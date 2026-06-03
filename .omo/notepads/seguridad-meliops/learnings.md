# Learnings - Seguridad MeliOps

## WSL NTFS Performance
- WSL NTFS mount (`/mnt/c/...`) is extremely slow for copying many small files (like virtual environments or node_modules).
- Running `uv sync` or `pytest` directly on the NTFS mount can time out.
- Solution: Copy the project to `/tmp/opencode/` (excluding `.venv`, `.git`, `.opencode`, `node_modules`), run `uv sync` and `pytest` there. It is extremely fast (takes less than 1 second to sync and run tests).

## PDF Size Validation
- Enforcing a 200 KB size limit on uploaded files using `file.file.seek(0, 2)` and `file.file.tell()` is efficient and prevents loading the entire file into memory.
- Always reset the file pointer using `file.file.seek(0)` after checking the size so that subsequent reads can read the entire file content.
- Assigning the result of `seek` to `_` avoids linter warnings about unused call results in basedpyright.
