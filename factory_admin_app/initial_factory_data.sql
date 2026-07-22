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
    seed.port_no,
    seed.group_no,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM (
    VALUES
        ('192.168.1.10', 502, 1)
) AS seed(ip_address, port_no, group_no)
WHERE NOT EXISTS (
    SELECT 1
    FROM recorder_ip existing
    WHERE existing.ip_address = seed.ip_address
      AND existing.group_no IS NOT DISTINCT FROM seed.group_no
);
