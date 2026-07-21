import pytest
from saichallenger.common.sai import Sai
from saichallenger.common.sai_data import SaiObjType

NULL_OID = "oid:0x0"

port_connector_attrs = Sai.get_obj_attrs(SaiObjType.PORT_CONNECTOR)


@pytest.fixture(scope="module", autouse=True)
def skip_all(testbed_instance):
    testbed = testbed_instance
    if testbed is not None and len(testbed.phy) != 1:
        pytest.skip(f'invalid for "{testbed.name}" testbed')


@pytest.fixture
def connector_oid(phy):
    connector_oids = phy.get_list(
        phy.switch_oid,
        "SAI_SWITCH_ATTR_PORT_CONNECTOR_LIST",
        NULL_OID,
    )

    if not connector_oids:
        pytest.skip("PHY does not have port connectors")

    return connector_oids[0]


@pytest.mark.parametrize(
    "attr,attr_type",
    port_connector_attrs,
)
def test_get_attr(phy, connector_oid, attr, attr_type):
    status, _ = phy.get_by_type(
        connector_oid,
        attr,
        attr_type,
        do_assert=False,
    )
    phy.assert_status_success(status)


def test_get_port_connector_attributes(phy, connector_oid):
    system_port_oid = phy.get(
        connector_oid,
        ["SAI_PORT_CONNECTOR_ATTR_SYSTEM_SIDE_PORT_ID"],
    ).oid()
    line_port_oid = phy.get(
        connector_oid,
        ["SAI_PORT_CONNECTOR_ATTR_LINE_SIDE_PORT_ID"],
    ).oid()

    assert system_port_oid in phy.port_oids
    assert line_port_oid in phy.port_oids
    assert system_port_oid != line_port_oid


@pytest.mark.xfail(
    reason="ValidateOnCreate does not check MANDATORY_ON_CREATE",
    strict=True,
)
def test_create_without_required_attributes_fails(phy):
    status, oid = phy.create(
        SaiObjType.PORT_CONNECTOR,
        [],
        do_assert=False,
    )

    try:
        assert status == "SAI_STATUS_MANDATORY_ATTRIBUTE_MISSING"
    finally:
        if status == "SAI_STATUS_SUCCESS":
            phy.remove(oid, do_assert=False)


@pytest.mark.xfail(
    reason="ValidateOnCreate does not check MANDATORY_ON_CREATE",
    strict=True,
)
@pytest.mark.parametrize(
    "missing_attr",
    [
        "SAI_PORT_CONNECTOR_ATTR_SYSTEM_SIDE_PORT_ID",
        "SAI_PORT_CONNECTOR_ATTR_LINE_SIDE_PORT_ID",
    ],
)
def test_create_with_one_required_attribute_missing_fails(
    phy,
    missing_attr,
):
    if len(phy.port_oids) < 2:
        pytest.skip("PHY does not have at least two ports")

    attrs = {
        "SAI_PORT_CONNECTOR_ATTR_SYSTEM_SIDE_PORT_ID": phy.port_oids[0],
        "SAI_PORT_CONNECTOR_ATTR_LINE_SIDE_PORT_ID": phy.port_oids[1],
    }
    attrs.pop(missing_attr)

    status, oid = phy.create(
        SaiObjType.PORT_CONNECTOR,
        list(sum(attrs.items(), ())),
        do_assert=False,
    )

    try:
        assert status == "SAI_STATUS_MANDATORY_ATTRIBUTE_MISSING"
    finally:
        if status == "SAI_STATUS_SUCCESS":
            phy.remove(oid, do_assert=False)


@pytest.mark.xfail(
    reason="NULL OID is accepted for PORT_CONNECTOR port attrs",
    strict=True,
)
@pytest.mark.parametrize(
    "attr",
    [
        "SAI_PORT_CONNECTOR_ATTR_SYSTEM_SIDE_PORT_ID",
        "SAI_PORT_CONNECTOR_ATTR_LINE_SIDE_PORT_ID",
    ],
)
def test_create_with_invalid_port_id_fails(phy, attr):
    if len(phy.port_oids) < 2:
        pytest.skip("PHY does not have at least two ports")

    attrs = [
        "SAI_PORT_CONNECTOR_ATTR_SYSTEM_SIDE_PORT_ID", phy.port_oids[0],
        "SAI_PORT_CONNECTOR_ATTR_LINE_SIDE_PORT_ID", phy.port_oids[1],
    ]
    attrs[attrs.index(attr) + 1] = NULL_OID

    status, oid = phy.create(
        SaiObjType.PORT_CONNECTOR,
        attrs,
        do_assert=False,
    )

    try:
        assert status in (
            "SAI_STATUS_INVALID_OBJECT_ID",
            "SAI_STATUS_INVALID_ATTR_VALUE_0",
            "SAI_STATUS_INVALID_ATTR_VALUE_1",
        )
    finally:
        if status == "SAI_STATUS_SUCCESS":
            phy.remove(oid, do_assert=False)


@pytest.mark.parametrize(
    "attr",
    [
        "SAI_PORT_CONNECTOR_ATTR_SYSTEM_SIDE_PORT_ID",
        "SAI_PORT_CONNECTOR_ATTR_LINE_SIDE_PORT_ID",
    ],
)
def test_set_create_only_port_attribute_fails(
    phy,
    connector_oid,
    attr,
):
    original_oid = phy.get(connector_oid, [attr]).oid()

    another_port_oid = next(
        (
            port_oid
            for port_oid in phy.port_oids
            if port_oid != original_oid
        ),
        None,
    )
    if another_port_oid is None:
        pytest.skip("PHY does not have another port")

    status = phy.set(
        connector_oid,
        [attr, another_port_oid],
        do_assert=False,
    )

    assert status == "SAI_STATUS_INVALID_ATTRIBUTE_0"
    assert phy.get(connector_oid, [attr]).oid() == original_oid


def test_set_failover_mode(phy, connector_oid):
    attr = "SAI_PORT_CONNECTOR_ATTR_FAILOVER_MODE"

    status, original = phy.get_by_type(
        connector_oid,
        attr,
        "sai_port_connector_failover_mode_t",
        do_assert=False,
    )
    assert status == "SAI_STATUS_SUCCESS"
    original_mode = original.value()

    if original_mode == "SAI_PORT_CONNECTOR_FAILOVER_MODE_PRIMARY":
        target_mode = "SAI_PORT_CONNECTOR_FAILOVER_MODE_SECONDARY"
    else:
        target_mode = "SAI_PORT_CONNECTOR_FAILOVER_MODE_PRIMARY"

    try:
        status = phy.set(
            connector_oid,
            [attr, target_mode],
            do_assert=False,
        )
        assert status == "SAI_STATUS_SUCCESS"

        status, data = phy.get_by_type(
            connector_oid,
            attr,
            "sai_port_connector_failover_mode_t",
            do_assert=False,
        )
        assert status == "SAI_STATUS_SUCCESS"
        assert data.value() == target_mode
    finally:
        phy.set(connector_oid, [attr, original_mode], do_assert=False)
