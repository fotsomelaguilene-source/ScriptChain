"""The application serves EXACTLY the operations of the specification, with the declared response models."""
import pytest

from tests.conftest import declared_schema, operations_served, spec_operations, success_codes, success_schema

pytestmark = pytest.mark.contract


def test_every_operation_of_the_spec_is_served_and_nothing_else(app):
    served = operations_served(app)                  # what app.openapi() documents
    assert set(served) == spec_operations()
    for (method, path), operation in sorted(served.items()):
        codes = {code for code in operation["responses"] if code.startswith("2")}
        assert codes == success_codes(method, path), (method, path)
        documented = success_schema(method, path)
        declared = declared_schema(app, operation, min(codes))
        assert declared, f"{method} {path} declares no response model"
        assert set(declared.get("properties", {})) == set(documented["properties"]), (method, path)
        assert set(declared.get("required", [])) == set(documented["required"]), (method, path)
