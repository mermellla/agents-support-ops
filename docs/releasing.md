# Releasing agents-support-ops

Releases use GitHub Actions OIDC rather than stored PyPI API tokens. The workflow publishes
the same tested wheel and source archive to TestPyPI, pauses for production approval, then
publishes to PyPI with attestations.

## One-time repository setup

1. Create GitHub environments named `testpypi` and `pypi`.
2. Add a required reviewer to the `pypi` environment. Leave `testpypi` unprotected so the
   validation upload can run first.
3. In TestPyPI, add a trusted publisher for owner `mermellla`, repository
   `agents-support-ops`, workflow `release.yml`, environment `testpypi`, and package
   `agents-support-ops`.
4. In PyPI, add the same trusted publisher with environment `pypi`. Use a pending publisher
   if the project does not exist yet.
5. Enable the dependency graph, Dependabot alerts, and dependency security updates in the
   repository security settings.
6. Protect `main` and require the CI jobs before merge.

No `PYPI_API_TOKEN` or `TEST_PYPI_API_TOKEN` secret is required.

## Release procedure

1. Confirm `pyproject.toml` and the changelog contain the intended version.
2. Run the documented local tests and build checks.
3. Publish a GitHub Release tagged `v<version>`.
4. Wait for the TestPyPI publish and clean-install verification.
5. Approve the protected `pypi` environment after reviewing those results.
6. Confirm the PyPI project shows the GitHub Actions provenance attestations.
7. Verify the attached SBOM and checksums, then install from a clean environment:

   ```bash
   pip install agents-support-ops==<version>
   python -c "import agents_support_ops; print(agents_support_ops.__version__)"
   ```

Consumers can verify the GitHub build attestation with `gh attestation verify` against the
downloaded wheel or source archive. Each release also attaches `ATTESTATIONS.txt` with direct
references to its build-provenance and SBOM attestations.
