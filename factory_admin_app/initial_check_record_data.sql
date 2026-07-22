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

INSERT INTO check_record (
    equipment_id,
    equipment_group_id,
    factory_id,
    employee_id,
    recorder_ip_id,
    record_time,
    check_hour,
    check_type,
    display_text,
    raw_value_json,
    created_at
)
SELECT
    e.id,
    eg.id,
    f.factory_id,
    u.id,
    ri.recorder_ip_id,
    CURRENT_DATE + TIME '08:00:00',
    8,
    '1H',
    '1Hチェック / テストデータ',
    json_build_object(
        'temperature_1', '180',
        'temperature_2', '175',
        'conveyor_speed', '12',
        'checker_1h', u.name,
        'checker_4h', ''
    ),
    CURRENT_TIMESTAMP
FROM equipment e
LEFT JOIN equipment_groups eg
    ON eg.name = '焼準'
JOIN factory f
    ON f.factory_name = '美原工場'
LEFT JOIN users u
    ON u.is_active = TRUE
LEFT JOIN recorder_ip ri
    ON ri.is_active = TRUE
WHERE e.name = 'SGNR-1'
  AND u.id IS NOT NULL
  AND ri.recorder_ip_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM check_record existing
      WHERE existing.equipment_id = e.id
        AND existing.check_type = '1H'
        AND existing.check_hour = 8
        AND DATE(existing.record_time) = CURRENT_DATE
  );
