#!/usr/bin/env python3
"""
Script to remove sample data functionality from the chat client.
"""

import re

# Read the file
with open('nlp_to_structured_data_chat_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove _load_sample_data method (lines ~148-160)
pattern = r'async def _load_sample_data\(self, session, data_type: str\):.*?print\("❌ Failed to load sample data"\)\n'
content = re.sub(pattern, '', content, flags=re.DOTALL)

# 2. Remove /sample command handler (lines ~413-434)
pattern = r'# Load sample command: /sample <type>.*?continue\n'
content = re.sub(pattern, '', content, flags=re.DOTALL)

# 3. Fix reload command to only handle files
old_reload = '''# Reload command
                    elif command == 'reload':
                        if not last_load_command:
                            print("❌ No previous data to reload. Use /load or /sample first.")
                            continue

                        print("🔄 Reloading data...")
                        try:
                            if last_load_command[0] == 'file':
                                _, file_path, file_type, metadata_path = last_load_command
                                await self._load_file_data(session, file_path, file_type, metadata_path or "")
                            else:  # sample
                                _, sample_type = last_load_command
                                await self._load_sample_data(session, sample_type)
                            print(f"✅ Data reloaded successfully!")
                        except Exception as e:
                            print(f"❌ Failed to reload: {e}")
                        continue'''

new_reload = '''# Reload command
                    elif command == 'reload':
                        if not last_load_command:
                            print("❌ No previous data to reload. Use /load first.")
                            continue

                        print("🔄 Reloading data...")
                        try:
                            _, file_path, file_type, metadata_path = last_load_command
                            await self._load_file_data(session, file_path, file_type, metadata_path or "")
                            print(f"✅ Data reloaded successfully!")
                        except Exception as e:
                            print(f"❌ Failed to reload: {e}")
                        continue'''

content = content.replace(old_reload, new_reload)

# 4. Replace all /sample references with /load
content = content.replace('Use /load or /sample to load data', 'Use /load to load data')
content = content.replace('Use /load or /sample first', 'Use /load first')
content = content.replace('   • /sample sales          - Try sample sales data', '   • /load                  - Load your data file interactively')
content = content.replace('   • /sample sales', '   • /load                  - Load data interactively')

# Write back
with open('nlp_to_structured_data_chat_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Successfully removed sample data functionality!")
print("Changes made:")
print("  - Removed _load_sample_data() method")
print("  - Removed /sample command handler")
print("  - Fixed /reload to only handle files")
print("  - Updated all references to use /load only")
