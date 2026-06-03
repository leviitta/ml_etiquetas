# Decisions - Seguridad MeliOps

## PDF Size Limit Validation
- **Decision**: Enforce a 200 KB size limit on uploaded files in `/extract` endpoint.
- **Rationale**: Prevent Denial of Service (DoS) attacks and Out of Memory (OOM) errors by rejecting large files before they are processed or saved to disk.
- **Implementation**: Use `file.file.seek(0, 2)` and `file.file.tell()` to check the size of the file-like object without reading it into memory, and reset the pointer with `file.file.seek(0)`.
