-- ============================================================================
-- 013_listing_invoice.sql
-- Link a material listing to an invoice document.
-- Without an invoice the risk evaluator flags the deal as "HIGHEST RISK".
-- ============================================================================

alter table material_listings
  add column invoice_document_id uuid
    references documents(id) on delete set null;

comment on column material_listings.invoice_document_id is
  'FK to the invoice document uploaded by the recycler for this deal. '
  'NULL means no invoice — the risk evaluator automatically sets validity_risk '
  'to "HIGHEST RISK" when this is absent.';

create index idx_material_listings_invoice on material_listings(invoice_document_id)
  where invoice_document_id is not null;
