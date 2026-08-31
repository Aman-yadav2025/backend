import os

def find_todos(root_dir):
    todos = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if '.venv' in dirpath or '__pycache__' in dirpath:
            continue
        for filename in filenames:
            if filename.endswith('.py'):
                filepath = os.path.join(dirpath, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if 'TODO' in line or 'FIXME' in line or 'NotImplemented' in line:
                                todos.append(f"{filepath}:{i+1}: {line.strip()}")
                except Exception:
                    pass
    with open('todos.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(todos))

if __name__ == '__main__':
    find_todos('.')
