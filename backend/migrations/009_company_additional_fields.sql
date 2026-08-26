CREATE TYPE material_type AS ENUM ('METAL', 'PLASTIC');

ALTER TABLE companies
    ADD COLUMN company_email TEXT NOT NULL DEFAULT '',
    ADD COLUMN mobile_number TEXT NOT NULL DEFAULT '',
    ADD COLUMN company_pan_number TEXT NOT NULL DEFAULT '',
    ADD COLUMN factory_address TEXT NOT NULL DEFAULT '',
    ADD COLUMN state TEXT NOT NULL DEFAULT '',
    ADD COLUMN city TEXT NOT NULL DEFAULT '',
    ADD COLUMN pincode TEXT NOT NULL DEFAULT '',
    ADD COLUMN company_website TEXT,
    ADD COLUMN designation TEXT NOT NULL DEFAULT '',
    ADD COLUMN material material_type NOT NULL DEFAULT 'METAL';

UPDATE companies SET gst_number = '' WHERE gst_number IS NULL;
ALTER TABLE companies ALTER COLUMN gst_number SET NOT NULL;
ALTER TABLE companies ALTER COLUMN gst_number SET DEFAULT '';

UPDATE companies SET contact_person_name = '' WHERE contact_person_name IS NULL;
ALTER TABLE companies ALTER COLUMN contact_person_name SET NOT NULL;
ALTER TABLE companies ALTER COLUMN contact_person_name SET DEFAULT '';

ALTER TABLE companies
    ALTER COLUMN company_email DROP DEFAULT,
    ALTER COLUMN mobile_number DROP DEFAULT,
    ALTER COLUMN company_pan_number DROP DEFAULT,
    ALTER COLUMN factory_address DROP DEFAULT,
    ALTER COLUMN state DROP DEFAULT,
    ALTER COLUMN city DROP DEFAULT,
    ALTER COLUMN pincode DROP DEFAULT,
    ALTER COLUMN designation DROP DEFAULT,
    ALTER COLUMN material DROP DEFAULT,
    ALTER COLUMN gst_number DROP DEFAULT,
    ALTER COLUMN contact_person_name DROP DEFAULT;
