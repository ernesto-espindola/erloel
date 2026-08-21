import sys, os

app_py   = sys.argv[1]
work_dir = sys.argv[2]
settings = sys.argv[3]

with open(app_py, 'r', encoding='utf-8') as f:
    lines = f.readlines()

patched = 0
out = []
for line in lines:
    s = line.strip()
    if s.startswith('WORKING_DIR') and 'Path(' in line and '=' in line and 'Template' not in line and 'RELEASE' not in line and 'OUTPUT' not in line and 'LOGO' not in line:
        out.append(f'WORKING_DIR   = Path(r"{work_dir}")\n')
        patched += 1
    elif s.startswith('SETTINGS_FILE') and 'Path(' in line and '=' in line:
        out.append(f'SETTINGS_FILE = Path(r"{settings}")\n')
        patched += 1
    else:
        out.append(line)

with open(app_py, 'w', encoding='utf-8') as f:
    f.writelines(out)

print(f'Paths patched OK ({patched} substitutions)')
