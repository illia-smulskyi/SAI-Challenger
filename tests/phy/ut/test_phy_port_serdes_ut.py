import pytest
from saichallenger.common.sai_data import SaiObjType

NULL_OID = "oid:0x0"

@pytest.fixture(scope="module", autouse=True)
def skip_all(testbed_instance):
    testbed = testbed_instance
    if testbed is not None and len(testbed.phy) != 1:
        pytest.skip('invalid for "{}" testbed'.format(testbed.name))


def get_port_serdes_oid(phy, port_oid):
    status, data = phy.get_by_type(
        port_oid,
        "SAI_PORT_ATTR_PORT_SERDES_ID",
        "sai_object_id_t",
        do_assert=False,
    )
    assert status == "SAI_STATUS_SUCCESS"
    return data.oid()


def get_serdes_port_oid(phy, serdes_oid):
    status, data = phy.get_by_type(
        serdes_oid,
        "SAI_PORT_SERDES_ATTR_PORT_ID",
        "sai_object_id_t",
        do_assert=False,
    )
    assert status == "SAI_STATUS_SUCCESS"
    return data.oid()


def get_s32_list(phy, oid, attr):
    status, data = phy.get_by_type(
        oid,
        attr,
        "sai_s32_list_t",
        do_assert=False,
    )
    assert status == "SAI_STATUS_SUCCESS"
    return data.to_list()


def find_port_by_lane_count(phy, lane_count):
    for port_oid in phy.port_oids:
        status, data = phy.get_by_type(
            port_oid,
            "SAI_PORT_ATTR_HW_LANE_LIST",
            "sai_u32_list_t",
            do_assert=False,
        )

        if status == "SAI_STATUS_SUCCESS":
            lanes = data.to_list()
            if len(lanes) == lane_count:
                return port_oid

    pytest.skip(f"PHY does not have a {lane_count}-lane port")


def make_list(values):
    return f"{len(values)}:" + ",".join(str(value) for value in values)


def create_serdes(phy, port_oid, lane_count, do_assert=True):
    preemphasis = list(range(1, lane_count + 1))
    tx_fir_pre1 = [-1] * lane_count
    tx_fir_main = [10] * lane_count

    attrs = [
        "SAI_PORT_SERDES_ATTR_PORT_ID",
        port_oid,
        "SAI_PORT_SERDES_ATTR_PREEMPHASIS",
        make_list(preemphasis),
        "SAI_PORT_SERDES_ATTR_TX_FIR_PRE1",
        make_list(tx_fir_pre1),
        "SAI_PORT_SERDES_ATTR_TX_FIR_MAIN",
        make_list(tx_fir_main),
    ]

    result = phy.create(
        SaiObjType.PORT_SERDES,
        attrs,
        do_assert=do_assert,
    )

    return result, {
        "SAI_PORT_SERDES_ATTR_PREEMPHASIS":
            [str(value) for value in preemphasis],
        "SAI_PORT_SERDES_ATTR_TX_FIR_PRE1":
            [str(value) for value in tx_fir_pre1],
        "SAI_PORT_SERDES_ATTR_TX_FIR_MAIN":
            [str(value) for value in tx_fir_main],
    }


def test_initial_port_serdes_id_is_null(phy):
    for port_oid in phy.port_oids:
        assert get_port_serdes_oid(phy, port_oid) == NULL_OID


@pytest.mark.parametrize("lane_count", [1, 2, 4])
def test_create_get_remove_port_serdes(phy, lane_count):
    port_oid = find_port_by_lane_count(phy, lane_count)

    assert get_port_serdes_oid(phy, port_oid) == NULL_OID

    serdes_oid, expected_attrs = create_serdes(
        phy,
        port_oid,
        lane_count,
    )

    try:
        # SERDES points to its port.
        assert get_serdes_port_oid(phy, serdes_oid) == port_oid

        # Port points back to its SERDES.
        assert get_port_serdes_oid(phy, port_oid) == serdes_oid

        # CREATE_ONLY lane attributes were persisted correctly.
        for attr, expected_value in expected_attrs.items():
            assert get_s32_list(phy, serdes_oid, attr) == expected_value
    finally:
        status = phy.remove(serdes_oid, do_assert=False)
        assert status == "SAI_STATUS_SUCCESS"

    # Removing SERDES must clear the port back-reference.
    assert get_port_serdes_oid(phy, port_oid) == NULL_OID


@pytest.mark.xfail(
    reason="ValidateOnCreate does not check MANDATORY_ON_CREATE",
    strict=True,
)
def test_create_port_serdes_without_port_id_fails(phy):
    status, oid = phy.create(
        SaiObjType.PORT_SERDES,
        [],
        do_assert=False,
    )

    try:
        assert status == "SAI_STATUS_MANDATORY_ATTRIBUTE_MISSING"
    finally:
        if status == "SAI_STATUS_SUCCESS":
            phy.remove(oid, do_assert=False)


def test_create_port_serdes_with_invalid_port_id_fails(phy):
    status, _ = phy.create(
        SaiObjType.PORT_SERDES,
        [
            "SAI_PORT_SERDES_ATTR_PORT_ID",
            NULL_OID,
        ],
        do_assert=False,
    )

    assert status in (
        "SAI_STATUS_INVALID_OBJECT_ID",
        "SAI_STATUS_INVALID_ATTR_VALUE_0",
    )


def test_create_second_serdes_for_same_port_fails(phy):
    port_oid = phy.port_oids[0]

    first_serdes_oid = phy.create(
        SaiObjType.PORT_SERDES,
        [
            "SAI_PORT_SERDES_ATTR_PORT_ID",
            port_oid,
        ],
    )

    try:
        status, _ = phy.create(
            SaiObjType.PORT_SERDES,
            [
                "SAI_PORT_SERDES_ATTR_PORT_ID",
                port_oid,
            ],
            do_assert=False,
        )

        assert status == "SAI_STATUS_OBJECT_IN_USE"
        assert get_port_serdes_oid(phy, port_oid) == first_serdes_oid
    finally:
        phy.remove(first_serdes_oid)

    assert get_port_serdes_oid(phy, port_oid) == NULL_OID


def test_set_port_id_after_serdes_create_fails(phy):
    if len(phy.port_oids) < 2:
        pytest.skip("PHY does not have at least two ports")

    port_oid = phy.port_oids[0]
    another_port_oid = phy.port_oids[1]

    serdes_oid = phy.create(
        SaiObjType.PORT_SERDES,
        [
            "SAI_PORT_SERDES_ATTR_PORT_ID",
            port_oid,
        ],
    )

    try:
        status = phy.set(
            serdes_oid,
            [
                "SAI_PORT_SERDES_ATTR_PORT_ID",
                another_port_oid,
            ],
            do_assert=False,
        )

        assert status == "SAI_STATUS_INVALID_ATTRIBUTE_0"
        assert get_serdes_port_oid(phy, serdes_oid) == port_oid
    finally:
        phy.remove(serdes_oid)


def test_set_create_only_lane_attribute_fails(phy):
    port_oid = phy.port_oids[0]

    status, data = phy.get_by_type(
        port_oid,
        "SAI_PORT_ATTR_HW_LANE_LIST",
        "sai_u32_list_t",
        do_assert=False,
    )
    assert status == "SAI_STATUS_SUCCESS"
    lane_count = len(data.to_list())

    serdes_oid = phy.create(
        SaiObjType.PORT_SERDES,
        [
            "SAI_PORT_SERDES_ATTR_PORT_ID",
            port_oid,
        ],
    )

    try:
        status = phy.set(
            serdes_oid,
            [
                "SAI_PORT_SERDES_ATTR_TX_FIR_MAIN",
                make_list([10] * lane_count),
            ],
            do_assert=False,
        )

        assert status == "SAI_STATUS_INVALID_ATTRIBUTE_0"
    finally:
        phy.remove(serdes_oid)


def test_remove_port_referenced_by_serdes_fails(phy):
    port_oid = phy.create(
        SaiObjType.PORT,
        [
            "SAI_PORT_ATTR_HW_LANE_LIST", "1:10000",
            "SAI_PORT_ATTR_SPEED", "100000",
            "SAI_PORT_ATTR_AUTO_NEG_MODE", "false",
            "SAI_PORT_ATTR_FEC_MODE", "SAI_PORT_FEC_MODE_NONE",
        ],
    )

    serdes_oid = None

    try:
        serdes_oid = phy.create(
            SaiObjType.PORT_SERDES,
            [
                "SAI_PORT_SERDES_ATTR_PORT_ID",
                port_oid,
            ],
        )

        status = phy.remove(port_oid, do_assert=False)
        assert status == "SAI_STATUS_OBJECT_IN_USE"
    finally:
        if serdes_oid is not None:
            phy.remove(serdes_oid, do_assert=False)

        phy.remove(port_oid, do_assert=False)