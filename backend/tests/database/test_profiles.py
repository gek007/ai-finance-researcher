import uuid
from unittest.mock import MagicMock

from app.database import profiles


def test_ensure_profile_upserts_by_id() -> None:
    user_id = uuid.uuid4()
    row = {"id": str(user_id), "email": "analyst@driftwood.test"}
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [row]

    result = profiles.ensure_profile(client, user_id, "analyst@driftwood.test")

    assert result == row
    client.table.assert_called_with("profiles")
    payload, kwargs = (
        client.table.return_value.upsert.call_args[0][0],
        client.table.return_value.upsert.call_args[1],
    )
    assert payload == {"id": str(user_id), "email": "analyst@driftwood.test"}
    assert kwargs == {"on_conflict": "id"}
