# frozen_string_literal: true

# This file contains tasks related to the generation of a configured architecture specification

require_relative "../../lib/yaml_loader"
require_relative "lib/arch_gen"

ARCH_GEN_DIR = Pathname.new(__FILE__).dirname

def arch_def_for(config_name)
  config_name = "_" if config_name.nil?
  @arch_defs ||= {}
  return @arch_defs[config_name] if @arch_defs.key?(config_name)

  @arch_defs[config_name] =
    if config_name == "_"
      ArchDef.new("_", $root / "gen" / "_" / "arch" / "arch_def.yaml")
    else
      ArchDef.new(
        config_name,
        $root / "gen" / config_name / "arch" / "arch_def.yaml",
        overlay_path: $root / "cfgs" / config_name / "arch_overlay"
      )
    end
end

file "#{$root}/.stamps/arch-gen.stamp" => (
  [
    "#{$root}/.stamps",
    "#{ARCH_GEN_DIR}/lib/arch_gen.rb",
    "#{$root}/lib/idl/ast.rb",
    "#{ARCH_GEN_DIR}/tasks.rake",
    __FILE__
  ] + Dir.glob($root / "arch" / "**" / "*.yaml")
) do |t|
  csr_hash = Dir.glob($root / "arch" / "csr" / "**" / "*.yaml").map do |f|
    csr_obj = YamlLoader.load(f, permitted_classes:[Date])
    csr_name = csr_obj.keys[0]
    csr_obj[csr_name]["name"] = csr_name
    csr_obj[csr_name]["fields"].map do |k, v|
      v["name"] = k
      [k, v]
    end
    csr_obj[csr_name]["__source"] = f
    [csr_name, csr_obj[csr_name]]
  end.to_h
  inst_hash = Dir.glob($root / "arch" / "inst" / "**" / "*.yaml").map do |f|
    inst_obj = YamlLoader.load(f, permitted_classes:[Date])
    inst_name = inst_obj.keys[0]
    inst_obj[inst_name]["name"] = inst_name
    inst_obj[inst_name]["__source"] = f
    [inst_name, inst_obj[inst_name]]
  end.to_h
  ext_hash = Dir.glob($root / "arch" / "ext" / "**" / "*.yaml").map do |f|
    ext_obj = YamlLoader.load(f, permitted_classes:[Date])
    ext_name = ext_obj.keys[0]
    ext_obj[ext_name]["name"] = ext_name
    ext_obj[ext_name]["__source"] = f
    [ext_name, ext_obj[ext_name]]
  end.to_h
  profile_class_hash = Dir.glob($root / "arch" / "profile_class" / "**" / "*.yaml").map do |f|
    profile_class_obj = YamlLoader.load(f, permitted_classes:[Date])
    profile_class_name = profile_class_obj.keys[0]
    profile_class_obj[profile_class_name]["name"] = profile_class_name
    profile_class_obj[profile_class_name]["__source"] = f
    [profile_class_name, profile_class_obj[profile_class_name]]
  end.to_h
  profile_release_hash = Dir.glob($root / "arch" / "profile_release" / "**" / "*.yaml").map do |f|
    profile_release_obj = YamlLoader.load(f, permitted_classes:[Date])
    profile_release_name = profile_release_obj.keys[0]
    profile_release_obj[profile_release_name]["name"] = profile_release_name
    profile_release_obj[profile_release_name]["__source"] = f
    [profile_release_name, profile_release_obj[profile_release_name]]
  end.to_h
  cert_class_hash = Dir.glob($root / "arch" / "certificate_class" / "**" / "*.yaml").map do |f|
    cert_class_obj = YamlLoader.load(f, permitted_classes:[Date])
    cert_class_name = cert_class_obj.keys[0]
    cert_class_obj[cert_class_name]["name"] = cert_class_name
    cert_class_obj[cert_class_name]["__source"] = f
    [cert_class_name, cert_class_obj[cert_class_name]]
  end.to_h
  cert_model_hash = Dir.glob($root / "arch" / "certificate_model" / "**" / "*.yaml").map do |f|
    cert_model_obj = YamlLoader.load(f, permitted_classes:[Date])
    cert_model_name = cert_model_obj.keys[0]
    cert_model_obj[cert_model_name]["name"] = cert_model_name
    cert_model_obj[cert_model_name]["__source"] = f
    [cert_model_name, cert_model_obj[cert_model_name]]
  end.to_h
  manual_hash = {}
  Dir.glob($root / "arch" / "manual" / "**" / "contents.yaml").map do |f|
    manual_version = YamlLoader.load(f, permitted_classes:[Date])
    manual_id = manual_version["manual"]
    unless manual_hash.key?(manual_id)
      manual_info_files = Dir.glob($root / "arch" / "manual" / "**" / "#{manual_id}.yaml")
      raise "Could not find manual info '#{manual_id}'.yaml, needed by #{f}" if manual_info_files.empty?
      raise "Found multiple manual infos '#{manual_id}'.yaml, needed by #{f}" if manual_info_files.size > 1

      manual_info_file = manual_info_files.first
      manual_hash[manual_id] = YamlLoader.load(manual_info_file, permitted_classes:[Date])
      manual_hash[manual_id]["__source"] = manual_info_file
      # TODO: schema validation
    end

    manual_hash[manual_id]["versions"] ||= []
    manual_hash[manual_id]["versions"] << YamlLoader.load(f, permitted_classes:[Date])
    # TODO: schema validation
    manual_hash[manual_id]["versions"].last["__source"] = f
  end

  arch_def = {
    "type" => "unconfigured",
    "instructions" => inst_hash,
    "extensions" => ext_hash,
    "csrs" => csr_hash,
    "profile_classes" => profile_class_hash,
    "profile_releases" => profile_release_hash,
    "certificate_classes" => cert_class_hash,
    "certificate_models" => cert_model_hash,
    "manuals" => manual_hash
  }

  dest = "#{$root}/gen/_/arch/arch_def.yaml"
  FileUtils.mkdir_p File.dirname(dest)
  File.write(dest, YAML.dump(arch_def))

  FileUtils.touch(t.name)
end

obj_model_files = Dir.glob($root / "lib" / "arch_obj_models" / "*.rb")
obj_model_files << ($root / "lib" / "arch_def.rb")

arch_files = Dir.glob($root / "arch" / "**" / "*.yaml")

# stamp to indicate completion of Arch Gen for a given config
rule %r{#{$root}/\.stamps/arch-gen-.*\.stamp} => proc { |tname|
  config_name = Pathname.new(tname).basename(".stamp").sub("arch-gen-", "")
  config_files =
    Dir.glob($root / "cfgs" / config_name / "arch_overlay" / "**" / "*.yaml") +
    [($root / "cfgs" / config_name / "params.yaml").to_s]
  [
    "#{$root}/.stamps",
    "#{ARCH_GEN_DIR}/lib/arch_gen.rb",
    "#{$root}/lib/idl/ast.rb",
    "#{ARCH_GEN_DIR}/tasks.rake",
    arch_files,
    config_files,
    
    # the stamp file is not actually dependent on the Ruby object model,
    # but in general we want to rebuild anything using this stamp when the object model changes
    obj_model_files.map(&:to_s)
  ].flatten
} do |t|
  config_name = Pathname.new(t.name).basename(".stamp").sub("arch-gen-", "")

  arch_gen = ArchGen.new(config_name)
  puts "Generating architecture definition in #{arch_gen.gen_dir.relative_path_from($root)}"

  arch_gen.generate

  puts "  Found #{arch_gen.implemented_csrs.size} CSRs"
  puts "  Found #{arch_gen.implemented_extensions.size} Extensions"
  puts "  Found #{arch_gen.implemented_instructions.size} Instructions"

  FileUtils.touch t.name
end

namespace :gen do
  desc "Generate the cfg-specific architecture files for config_name"
  task :cfg_arch, [:config_name] do |_t, args|
    raise "No config '#{args[:config_name]}' found in cfgs/" unless ($root / "cfgs" / args[:config_name]).directory?

    Rake::Task["#{$root}/.stamps/arch-gen-#{args[:config_name]}.stamp"].invoke(args[:config_name])
  end

  desc "Generate a unified architecture file (configuration independent)"
  task :arch do
    Rake::Task["#{$root}/.stamps/arch-gen.stamp"].invoke
  end
end

namespace :validate do
  desc "Validate that a configuration folder valid for the list of extensions it claims to implement"
  task :cfg, [:config_name] do |_t, args|
    raise "No config '#{args[:config_name]}' found in cfgs/" unless ($root / "cfgs" / args[:config_name]).directory?

    ArchGen.new(args[:config_name]).validate_params

    puts "Success! The '#{args[:config_name]}' configuration passes validation checks"
  end
end
