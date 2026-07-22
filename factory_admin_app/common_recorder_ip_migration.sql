-- Target: public.recorder_ip only in common_db_stg
-- Purpose:
-- 1. Drop legacy UNIQUE(ip_address) if it exists
-- 2. Reject migration when group_no contains NULL
-- 3. Reject migration when (ip_address, group_no) duplicates exist
-- 4. Set port_no DEFAULT 502
-- 5. Set group_no NOT NULL
-- 6. Add UNIQUE(ip_address, group_no)

DO $$
DECLARE
    null_group_count bigint;
    duplicate_count bigint;
BEGIN
    SELECT COUNT(*)
    INTO null_group_count
    FROM public.recorder_ip
    WHERE group_no IS NULL;

    IF null_group_count > 0 THEN
        RAISE EXCEPTION
            'Migration stopped: public.recorder_ip.group_no contains % NULL row(s). Fill group_no before applying NOT NULL.',
            null_group_count;
    END IF;

    SELECT COUNT(*)
    INTO duplicate_count
    FROM (
        SELECT ip_address, group_no
        FROM public.recorder_ip
        GROUP BY ip_address, group_no
        HAVING COUNT(*) > 1
    ) duplicated_pairs;

    IF duplicate_count > 0 THEN
        RAISE EXCEPTION
            'Migration stopped: public.recorder_ip has % duplicated (ip_address, group_no) pair(s). Resolve duplicates before adding UNIQUE constraint.',
            duplicate_count;
    END IF;
END $$;

DO $$
DECLARE
    old_constraint_name text;
BEGIN
    FOR old_constraint_name IN
        SELECT constraint_name
        FROM (
            SELECT
                tc.constraint_name,
                COUNT(*) AS column_count,
                MAX(kcu.column_name) AS only_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
               AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'UNIQUE'
              AND tc.table_schema = 'public'
              AND tc.table_name = 'recorder_ip'
            GROUP BY tc.constraint_name
        ) unique_constraints
        WHERE column_count = 1
          AND only_column_name = 'ip_address'
    LOOP
        EXECUTE format(
            'ALTER TABLE public.recorder_ip DROP CONSTRAINT %I',
            old_constraint_name
        );
    END LOOP;
END $$;

ALTER TABLE public.recorder_ip
    ALTER COLUMN port_no SET DEFAULT 502;

ALTER TABLE public.recorder_ip
    ALTER COLUMN group_no SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class rel
            ON rel.oid = con.conrelid
        JOIN pg_namespace nsp
            ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'recorder_ip'
          AND con.conname = 'uq_recorder_ip_ip_address_group_no'
    ) THEN
        ALTER TABLE public.recorder_ip
            ADD CONSTRAINT uq_recorder_ip_ip_address_group_no
            UNIQUE (ip_address, group_no);
    END IF;
END $$;

-- Optional investigation queries before retrying if the migration stops:
-- SELECT recorder_ip_id, ip_address, port_no, group_no
-- FROM public.recorder_ip
-- WHERE group_no IS NULL
-- ORDER BY recorder_ip_id;
--
-- SELECT ip_address, group_no, COUNT(*) AS duplicate_count
-- FROM public.recorder_ip
-- GROUP BY ip_address, group_no
-- HAVING COUNT(*) > 1
-- ORDER BY ip_address, group_no;
