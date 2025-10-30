import yaml
import os
import re

# -----------------------------
# Recursive prefix function with lookup
# -----------------------------
def recursive_prefix_lookup(data, prefix, keys_to_prefix, lookup):
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if key in keys_to_prefix and isinstance(value, str):
                if not value.startswith(prefix):
                    new_value = f"{prefix}{value}"
                    lookup[value] = new_value
                    new_data[key] = new_value
                else:
                    new_data[key] = value
            else:
                new_data[key] = recursive_prefix_lookup(value, prefix, keys_to_prefix, lookup)
        return new_data
    elif isinstance(data, list):
        return [recursive_prefix_lookup(item, prefix, keys_to_prefix, lookup) for item in data]
    else:
        return data

# -----------------------------
# Diff function for reporting changes
# -----------------------------
def diff_dict(d1, d2, path=""):
    changes = []
    if isinstance(d1, dict) and isinstance(d2, dict):
        for k in d1.keys() | d2.keys():
            p = f"{path}.{k}" if path else k
            if k in d1 and k in d2:
                changes.extend(diff_dict(d1[k], d2[k], p))
            elif k in d1:
                changes.append((p, d1[k], None))
            else:
                changes.append((p, None, d2[k]))
    elif isinstance(d1, list) and isinstance(d2, list):
        for i, (v1, v2) in enumerate(zip(d1, d2)):
            p = f"{path}[{i}]"
            changes.extend(diff_dict(v1, v2, p))
        for i in range(len(d1), len(d2)):
            changes.append((f"{path}[{i}]", None, d2[i]))
        for i in range(len(d2), len(d1)):
            changes.append((f"{path}[{i}]", d1[i], None))
    else:
        if d1 != d2:
            changes.append((path, d1, d2))
    return changes

# -----------------------------
# Fix malformed block scalars
# -----------------------------
def fix_block_scalars(text):
    def repl(m):
        return m.group(1) + "\n  " + m.group(2)
    pattern = re.compile(r"(\|\s*)([^\n\s])")
    text = pattern.sub(repl, text)
    pattern2 = re.compile(r"(\>\s*)([^\n\s])")
    text = pattern2.sub(repl, text)
    return text

# -----------------------------
# Ignore unknown YAML tags like !unsafe
# -----------------------------
def ignore_unknown_tags(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    else:
        return None

yaml.SafeLoader.add_multi_constructor('!', ignore_unknown_tags)

# -----------------------------
# Process a YAML file
# -----------------------------
def process_yaml_file(filepath, prefix, keys_to_prefix, lookup):
    with open(filepath, "r") as f:
        raw_content = f.read()

    # Fix block scalar issues
    raw_content = fix_block_scalars(raw_content)

    # Load YAML safely
    original_data = yaml.safe_load(raw_content)

    # Apply prefix
    updated_data = recursive_prefix_lookup(original_data, prefix, keys_to_prefix, lookup)
    diffs = diff_dict(original_data, updated_data)

    # Dump YAML with block style for multiline strings
    def represent_multiline_str(dumper, data):
        if "\n" in data or any(c in data for c in ['"', "'", "\\", "<", ">"]):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, represent_multiline_str)

    with open(filepath, "w") as f:
        yaml.safe_dump(updated_data, f, sort_keys=False, allow_unicode=True)

    print(f"✅ Processed: {os.path.basename(filepath)}")
    if diffs:
        print("Changes made:")
        for path, old, new in diffs:
            print(f"  {path}: {old} -> {new}")
    else:
        print("No changes detected.")

# -----------------------------
# Main entry point
# -----------------------------
if __name__ == "__main__":
    prefix = input("Enter prefix to prepend (e.g., dev_): ").strip()
    lookup_table = {}

    file_key_map = {
        "orgs.yaml": ["name"],
        "projects.yaml": ["name", "organization"],
        "teams.yaml": ["name", "organization"],
        "schedules.yaml": ["name", "unified_job_template"],
        "inventories.yaml": ["name", "organization"],
        "job_templates.yaml": ["name", "organization", "project", "inventory", "credentials"],
        "notification_templates.yaml": ["name", "organization"],
        "workflow_job_templates.yaml": ["name", "organization", "workflow_job_template", "unified_job_template"],
    }

    for filename, keys in file_key_map.items():
        if os.path.exists(filename):
            try:
                process_yaml_file(filename, prefix, keys, lookup_table)
            except Exception as e:
                print(f"❌ Failed to process {filename}: {e}")
        else:
            print(f"⚠️ Skipping {filename} (not found)")

    print("\nLookup table (old -> new values):")
    for old, new in lookup_table.items():
        print(f"  {old} -> {new}")
