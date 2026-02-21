#!/usr/bin/env ruby
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Custom Extension Compliance Checker
#
# Reports potential RISC-V encoding convention issues for custom extension overlays.
# All output is advisory (WARN/INFO) — not errors.
#
# Usage:
#   bundle exec ruby tools/check_custom_compliance.rb [CONFIG]
#
# CONFIG defaults to "aifoundry". Any config name from cfgs/ can be used.

require "bundler/setup"
require "udb/resolver"

# ---------------------------------------------------------------------------
# Standard 32-bit base opcode map (bits [6:2], with bits [1:0] = 11)
# Source: RISC-V ISA Manual, Table 34 (RV32/64G Opcode Map)
# ---------------------------------------------------------------------------
STANDARD_OPCODES = {
  "0000011" => "LOAD",
  "0000111" => "LOAD-FP",
  "0001111" => "MISC-MEM",
  "0010011" => "OP-IMM",
  "0010111" => "AUIPC",
  "0011011" => "OP-IMM-32",
  "0100011" => "STORE",
  "0100111" => "STORE-FP",
  "0101111" => "AMO",
  "0110011" => "OP",
  "0110111" => "LUI",
  "0111011" => "OP-32",
  "1000011" => "MADD",
  "1000111" => "MSUB",
  "1001011" => "NMSUB",
  "1001111" => "NMADD",
  "1010011" => "OP-FP",
  "1010111" => "OP-V",
  "1100011" => "BRANCH",
  "1100111" => "JALR",
  "1101011" => "reserved",
  "1101111" => "JAL",
  "1110011" => "SYSTEM",
  "1110111" => "OP-VE",
  "1111011" => "custom-3",
  "1111111" => "reserved",
  # 48-bit+ hint
  "0001011" => "custom-0",
  "0101011" => "custom-1",
  "1011011" => "custom-2"
}.freeze

CUSTOM_OPCODE_SPACES = %w[custom-0 custom-1 custom-2 custom-3].freeze

# Standard register variable positions (bit ranges)
STANDARD_VAR_POSITIONS = {
  "rs1"  => [19, 18, 17, 16, 15],
  "xs1"  => [19, 18, 17, 16, 15],
  "fs1"  => [19, 18, 17, 16, 15],
  "rs2"  => [24, 23, 22, 21, 20],
  "xs2"  => [24, 23, 22, 21, 20],
  "fs2"  => [24, 23, 22, 21, 20],
  "rd"   => [11, 10, 9, 8, 7],
  "xd"   => [11, 10, 9, 8, 7],
  "fd"   => [11, 10, 9, 8, 7],
  "rs3"  => [31, 30, 29, 28, 27],
  "fs3"  => [31, 30, 29, 28, 27],
  "ms1"  => [17, 16, 15],
  "ms2"  => [22, 21, 20],
  "md"   => [9, 8, 7]
}.freeze

# Assembly operand name -> expected encoding variable names
ASM_TO_VAR = {
  "xd"  => %w[rd xd],
  "xs1" => %w[rs1 xs1],
  "xs2" => %w[rs2 xs2],
  "fd"  => %w[rd fd],
  "fs1" => %w[rs1 fs1],
  "fs2" => %w[rs2 fs2],
  "fs3" => %w[rs3 fs3],
  "rd"  => %w[rd],
  "rs1" => %w[rs1],
  "rs2" => %w[rs2],
  "rs3" => %w[rs3],
  "md"  => %w[md],
  "ms1" => %w[ms1],
  "ms2" => %w[ms2]
}.freeze

# ---------------------------------------------------------------------------
# Result collector
# ---------------------------------------------------------------------------
class ComplianceResult
  attr_reader :findings

  def initialize
    @findings = Hash.new { |h, k| h[k] = [] }
  end

  def add(category, severity, inst_name, message)
    @findings[category] << { severity: severity, inst: inst_name, message: message }
  end

  def print_report
    total = 0
    counts = Hash.new(0)

    @findings.keys.sort.each do |category|
      items = @findings[category]
      puts "\n== #{category} (#{items.size}) =="
      items.sort_by { |f| [f[:severity], f[:inst]] }.each do |f|
        tag = f[:severity].upcase
        puts "  [#{tag}] #{f[:inst]}: #{f[:message]}"
        counts[f[:severity]] += 1
        total += 1
      end
    end

    puts "\n--- Summary ---"
    puts "  WARN: #{counts['warn']}  INFO: #{counts['info']}  Total: #{total}"
  end
end

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Extract bits[6:0] from a 32-char match string (MSB-first)
def extract_opcode(format_str)
  return nil unless format_str.size >= 7

  format_str[-7..]
end

# Recursively collect extension names from a definedBy hash/string
def collect_extension_names(defined_by)
  names = []
  case defined_by
  when String
    names << defined_by
  when Hash
    if defined_by.key?("name")
      names << defined_by["name"]
    else
      defined_by.each_value do |v|
        case v
        when Array
          v.each { |item| names.concat(collect_extension_names(item)) }
        else
          names.concat(collect_extension_names(v))
        end
      end
    end
  end
  names
end

# Parse assembly string to extract operand tokens (skip the mnemonic)
def parse_assembly_operands(assembly_str)
  return [] if assembly_str.nil? || assembly_str.strip.empty?

  # Assembly format: "mnemonic op1, op2, op3" or "mnemonic op1, op2(op3)"
  parts = assembly_str.strip.split(/\s+/, 2)
  return [] if parts.size < 2

  operand_str = parts[1]
  # Split by comma and parentheses, strip whitespace
  operand_str.split(/[,()]+/).map(&:strip).reject(&:empty?)
end

# Determine if an instruction is custom based on data_path
def custom_instruction?(inst)
  path = inst.data_path.to_s
  # Custom instructions live under extension dirs starting with X
  # In the resolved spec, they appear under inst/X<name>/
  path_parts = path.split("/")
  inst_idx = path_parts.index("inst")
  return false if inst_idx.nil?

  ext_dir = path_parts[inst_idx + 1]
  return false if ext_dir.nil?

  ext_dir.start_with?("X")
end

# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def check_opcode_space(inst, xlen, results)
  format_str = inst.encoding(xlen).format

  # Only classify 32-bit encodings — compressed (16-bit) use a different opcode scheme
  return unless format_str.size == 32

  opcode = extract_opcode(format_str)
  return if opcode.nil?

  # Replace don't-cares with 0 for classification (only matters for bits 6:0)
  opcode_fixed = opcode.gsub("-", "0")
  category = STANDARD_OPCODES[opcode_fixed]

  if category.nil?
    # Check if bits vary (have '-' in opcode region) making classification ambiguous
    if opcode.include?("-")
      results.add("1. Opcode Space", "info", inst.name,
        "opcode bits[6:0]=#{opcode} contain variable bits — cannot classify uniquely")
    else
      results.add("1. Opcode Space", "info", inst.name,
        "uses unassigned opcode space (bits[6:0]=#{opcode})")
    end
  elsif CUSTOM_OPCODE_SPACES.include?(category)
    # OK — custom opcode space, no issue
  elsif category == "reserved"
    results.add("1. Opcode Space", "info", inst.name,
      "uses reserved opcode space (bits[6:0]=#{opcode})")
  else
    results.add("1. Opcode Space", "warn", inst.name,
      "uses standard opcode space #{category} (bits[6:0]=#{opcode})")
  end
end

def check_collisions(custom_insts, standard_insts, xlen, results)
  custom_insts.each do |cinst|
    next unless cinst.defined_in_base?(xlen)

    cenc = cinst.encoding(xlen)
    standard_insts.each do |sinst|
      next unless sinst.defined_in_base?(xlen)
      next if cinst.name == sinst.name

      senc = sinst.encoding(xlen)
      # Only compare same-width encodings
      next unless cenc.format.size == senc.format.size

      if cenc.indistinguishable?(senc)
        results.add("2. Collision Detection", "warn", cinst.name,
          "encoding indistinguishable from standard instruction '#{sinst.name}'")
      end
    end
  end
end

def check_variable_conventions(inst, xlen, results)
  # Standard positions only apply to 32-bit encodings
  return unless inst.encoding(xlen).format.size == 32

  inst.decode_variables(xlen).each do |var|
    expected_bits = STANDARD_VAR_POSITIONS[var.name]
    next if expected_bits.nil?

    actual_bits = var.location_bits.sort.reverse
    next if actual_bits == expected_bits

    results.add("3. Variable Name Convention", "warn", inst.name,
      "variable '#{var.name}' at bits #{var.location_bits.sort.reverse.inspect} " \
      "but standard position is #{expected_bits.inspect}")
  end
end

def check_assembly_encoding_consistency(inst, xlen, results)
  asm = inst.assembly
  return if asm.nil?

  operands = parse_assembly_operands(asm)
  var_names = inst.decode_variables(xlen).map(&:name)

  operands.each do |op|
    expected_vars = ASM_TO_VAR[op]
    if expected_vars
      unless expected_vars.any? { |ev| var_names.include?(ev) }
        results.add("4. Assembly-Encoding Consistency", "warn", inst.name,
          "assembly operand '#{op}' has no matching encoding variable " \
          "(expected one of #{expected_vars.inspect}, found #{var_names.inspect})")
      end
    else
      # For non-register operands (immediates, etc.), check if there's any variable
      # We only flag if no variable at all could correspond
      unless var_names.any? { |vn| vn.include?(op) || op.include?(vn) }
        results.add("4. Assembly-Encoding Consistency", "info", inst.name,
          "assembly operand '#{op}' has no obvious encoding variable match " \
          "(variables: #{var_names.inspect})")
      end
    end
  end
end

def check_encoding_format_integrity(inst, xlen, results)
  enc = inst.encoding(xlen)
  format_str = enc.format

  # Check bits[1:0] == 11 for 32-bit instructions
  base = inst.data["base"] || 32
  if base == 32 && format_str.size == 32
    low_bits = format_str[-2..]
    if low_bits != "11"
      results.add("5. Encoding Format Integrity", "warn", inst.name,
        "bits[1:0]='#{low_bits}' but expected '11' for base-32 instruction")
    end
  end

  # Check match string length
  if format_str.size != 32 && format_str.size != 16 && format_str.size != 48
    results.add("5. Encoding Format Integrity", "warn", inst.name,
      "match string is #{format_str.size} bits (expected 16, 32, or 48)")
  end

  # Check bit coverage: every '-' should be covered by a variable,
  # every '0'/'1' should not be
  var_bits = Set.new
  enc.decode_variables.each do |var|
    var.location_bits.each { |b| var_bits.add(b) }
  end

  format_str.size.times do |i|
    bit_idx = format_str.size - 1 - i
    char = format_str[i]

    if char == "-"
      unless var_bits.include?(bit_idx)
        results.add("5. Encoding Format Integrity", "warn", inst.name,
          "bit #{bit_idx} is '-' but not covered by any decode variable")
      end
    else
      if var_bits.include?(bit_idx)
        results.add("5. Encoding Format Integrity", "warn", inst.name,
          "bit #{bit_idx} is fixed ('#{char}') but also covered by a decode variable")
      end
    end
  end
end

def check_extension_path_consistency(inst, results)
  defined_by = inst.data["definedBy"]
  return if defined_by.nil?

  ext_names = collect_extension_names(defined_by)
  return if ext_names.empty?

  # Extract the extension directory from the data_path
  path_parts = inst.data_path.to_s.split("/")
  inst_idx = path_parts.index("inst")
  return if inst_idx.nil?

  ext_dir = path_parts[inst_idx + 1]
  return if ext_dir.nil?

  unless ext_names.any? { |en| en == ext_dir }
    results.add("6. Extension Path Consistency", "warn", inst.name,
      "file is under inst/#{ext_dir}/ but definedBy lists #{ext_names.inspect}")
  end
end

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main
  config_name = ARGV[0] || "aifoundry"

  # Validate config exists before any output
  cfg_path = Pathname.new(Udb.repo_root) / "cfgs" / "#{config_name}.yaml"
  unless cfg_path.exist?
    $stderr.puts "ERROR: Config '#{config_name}' not found at #{cfg_path}"
    $stderr.puts "Available configs:"
    Dir[Udb.repo_root / "cfgs" / "*.yaml"].sort.each do |f|
      $stderr.puts "  #{File.basename(f, '.yaml')}"
    end
    exit 1
  end

  puts "Custom Extension Compliance Checker"
  puts "Config: #{config_name}"
  puts "=" * 60

  # Load architecture
  puts "Loading architecture (this may take a moment)..."
  resolver = Udb::Resolver.new
  cfg_arch = resolver.cfg_arch_for(config_name)

  # Get all instructions
  all_instructions =
    if cfg_arch.fully_configured?
      cfg_arch.transitive_implemented_instructions
    else
      cfg_arch.not_prohibited_instructions
    end

  # Partition into custom vs standard
  custom_insts = all_instructions.select { |inst| custom_instruction?(inst) }
  standard_insts = all_instructions.reject { |inst| custom_instruction?(inst) }

  puts "Total instructions: #{all_instructions.size}"
  puts "  Custom:   #{custom_insts.size}"
  puts "  Standard: #{standard_insts.size}"

  results = ComplianceResult.new

  # Always check both XLENs — instructions declare which bases they support
  xlens = [32, 64]

  # Run checks on each custom instruction
  custom_insts.each do |inst|
    checked = false
    xlens.each do |xlen|
      next unless inst.defined_in_base?(xlen)

      checked = true
      check_opcode_space(inst, xlen, results)
      check_variable_conventions(inst, xlen, results)
      check_assembly_encoding_consistency(inst, xlen, results)
      check_encoding_format_integrity(inst, xlen, results)
    end
    unless checked
      results.add("0. Skipped", "info", inst.name,
        "not defined in any checked XLEN (base=#{inst.base.inspect})")
    end
    check_extension_path_consistency(inst, results)
  end

  # Collision detection (custom vs standard) — run per xlen
  xlens.each do |xlen|
    check_collisions(custom_insts, standard_insts, xlen, results)
  end

  # Print report
  if results.findings.empty?
    puts "\nNo compliance issues found."
  else
    results.print_report
  end
end

main
