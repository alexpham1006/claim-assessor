from pathlib import Path

import pytest

from claim_assessor.infrastructure.reference_data import ReferenceData


@pytest.fixture(scope="session")
def reference_data() -> ReferenceData:
    return ReferenceData(Path("data"))
