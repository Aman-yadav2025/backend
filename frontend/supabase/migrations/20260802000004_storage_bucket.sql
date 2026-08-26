-- Create the compliance-documents storage bucket
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'compliance-documents',
  'compliance-documents',
  false,                            -- private bucket; access via signed URLs only
  10485760,                         -- 10 MB per file
  ARRAY['application/pdf', 'image/png', 'image/jpeg']
)
on conflict (id) do nothing;

-- RLS: authenticated users can upload into their own folder (profile_id prefix)
create policy "Users upload own documents"
  on storage.objects for insert
  to authenticated
  with check (
    bucket_id = 'compliance-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- RLS: authenticated users can read their own documents
create policy "Users read own documents"
  on storage.objects for select
  to authenticated
  using (
    bucket_id = 'compliance-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- RLS: authenticated users can delete their own documents
create policy "Users delete own documents"
  on storage.objects for delete
  to authenticated
  using (
    bucket_id = 'compliance-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Service role can read all (for admin verification workflows)
create policy "Service role full access"
  on storage.objects for all
  to service_role
  using (bucket_id = 'compliance-documents')
  with check (bucket_id = 'compliance-documents');
