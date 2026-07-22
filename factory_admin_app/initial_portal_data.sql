-- Assumption:
-- equipment_groups(id, name)
-- equipment(id, name, group_id)
-- users(id, employee_code, password, name, is_active, created_at, factory, is_master)
-- factory / recorder_ip / furnace_recorder_map already use the structures handled by this workspace

INSERT INTO factory (
    factory_name,
    display_order,
    is_active,
    created_at,
    updated_at
)
SELECT
    seed.factory_name,
    seed.display_order,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM (
    VALUES
        ('加西工場', 10),
        ('美原工場', 20),
        ('岐阜工場', 30)
) AS seed(factory_name, display_order)
WHERE NOT EXISTS (
    SELECT 1
    FROM factory existing
    WHERE existing.factory_name = seed.factory_name
);

INSERT INTO recorder_ip (
    ip_address,
    port_no,
    group_no,
    is_active,
    created_at,
    updated_at
)
SELECT
    seed.ip_address,
    502,
    seed.group_no,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM (
    VALUES
        ('192.168.203.55', 1),
        ('192.168.203.55', 2),
        ('192.168.203.56', 1)
) AS seed(ip_address, group_no)
WHERE NOT EXISTS (
    SELECT 1
    FROM recorder_ip existing
    WHERE existing.ip_address = seed.ip_address
      AND existing.group_no = seed.group_no
);

INSERT INTO equipment_groups (id, name)
SELECT *
FROM (
    VALUES
        ('11111111-1111-1111-1111-111111111111'::uuid, '焼準'),
        ('22222222-2222-2222-2222-222222222222'::uuid, 'ピット'),
        ('33333333-3333-3333-3333-333333333333'::uuid, 'バッチ')
) AS seed(id, name)
WHERE NOT EXISTS (
    SELECT 1
    FROM equipment_groups existing
    WHERE existing.id = seed.id
);

INSERT INTO equipment (id, name, group_id)
SELECT *
FROM (
    VALUES
        ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'::uuid, 'SGNR-1', '11111111-1111-1111-1111-111111111111'::uuid),
        ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1'::uuid, 'PG-1', '22222222-2222-2222-2222-222222222222'::uuid),
        ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'::uuid, 'PG-2', '22222222-2222-2222-2222-222222222222'::uuid),
        ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb3'::uuid, 'PG-5', '22222222-2222-2222-2222-222222222222'::uuid),
        ('cccccccc-cccc-cccc-cccc-ccccccccccc1'::uuid, 'BQ-1', '33333333-3333-3333-3333-333333333333'::uuid),
        ('cccccccc-cccc-cccc-cccc-ccccccccccc2'::uuid, 'BQ-2', '33333333-3333-3333-3333-333333333333'::uuid)
) AS seed(id, name, group_id)
WHERE NOT EXISTS (
    SELECT 1
    FROM equipment existing
    WHERE existing.id = seed.id
);

INSERT INTO users (
    id,
    employee_code,
    password,
    name,
    is_active,
    created_at,
    factory,
    is_master
)
SELECT
    seed.id,
    seed.employee_code,
    seed.password,
    seed.name,
    TRUE,
    CURRENT_TIMESTAMP,
    seed.factory,
    FALSE
FROM (
    VALUES
        ('dddddddd-dddd-dddd-dddd-ddddddddddd1'::uuid, '1001', 'dummy-password', '山田太郎', '美原工場'),
        ('dddddddd-dddd-dddd-dddd-ddddddddddd2'::uuid, '1002', 'dummy-password', '佐藤花子', '加西工場')
) AS seed(id, employee_code, password, name, factory)
WHERE NOT EXISTS (
    SELECT 1
    FROM users existing
    WHERE existing.employee_code = seed.employee_code
);

INSERT INTO furnace_recorder_map (
    equipment_id,
    equipment_group_id,
    factory_id,
    recorder_ip_id,
    csv_file_name,
    is_active,
    created_at,
    updated_at
)
SELECT
    e.id,
    e.group_id,
    f.factory_id,
    ri.recorder_ip_id,
    seed.csv_file_name,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM (
    VALUES
        ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'::uuid, 'single_sgnr_1.csv', '美原工場', '192.168.203.55', 1),
        ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1'::uuid, 'pit_pg_1.csv', '美原工場', '192.168.203.55', 1),
        ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'::uuid, 'pit_pg_2.csv', '美原工場', '192.168.203.55', 2),
        ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb3'::uuid, 'pit_pg_5.csv', '美原工場', '192.168.203.56', 1),
        ('cccccccc-cccc-cccc-cccc-ccccccccccc1'::uuid, 'batch_bq_1.csv', '加西工場', '192.168.203.55', 1),
        ('cccccccc-cccc-cccc-cccc-ccccccccccc2'::uuid, 'batch_bq_2.csv', '加西工場', '192.168.203.55', 2)
) AS seed(equipment_id, csv_file_name, factory_name, ip_address, group_no)
JOIN equipment e
    ON e.id = seed.equipment_id
JOIN factory f
    ON f.factory_name = seed.factory_name
JOIN recorder_ip ri
    ON ri.ip_address = seed.ip_address
   AND ri.group_no = seed.group_no
WHERE NOT EXISTS (
    SELECT 1
    FROM furnace_recorder_map existing
    WHERE existing.equipment_id = e.id
      AND existing.recorder_ip_id = ri.recorder_ip_id
      AND existing.csv_file_name = seed.csv_file_name
);
