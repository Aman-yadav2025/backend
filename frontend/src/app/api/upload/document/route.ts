import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createClient as createServerClient } from '../../../../../utils/supabase/server';
import { createServiceClient } from '../../../../../utils/supabase/service';

const ALLOWED_MIME = ['application/pdf', 'image/png', 'image/jpeg'];
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB
const BUCKET = 'compliance-documents';

export async function POST(req: NextRequest) {
  try {
    // 1. Auth
    const cookieStore = await cookies();
    const supabase = createServerClient(cookieStore);
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized.' }, { status: 401 });
    }

    // 2. Parse multipart form
    const form = await req.formData();
    const file = form.get('file') as File | null;
    const docType = form.get('docType') as string | null;

    if (!file || !docType) {
      return NextResponse.json({ error: 'file and docType are required.' }, { status: 400 });
    }

    // 3. Validate mime type and size
    if (!ALLOWED_MIME.includes(file.type)) {
      return NextResponse.json(
        { error: 'Only PDF, PNG, and JPEG files are accepted.' },
        { status: 400 },
      );
    }

    if (file.size > MAX_BYTES) {
      return NextResponse.json(
        { error: `File is too large. Maximum size is 10 MB.` },
        { status: 400 },
      );
    }

    // 4. Build a deterministic storage path: {userId}/{docType}/{timestamp}-{filename}
    const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80);
    const storagePath = `${user.id}/${docType}/${Date.now()}-${safeName}`;

    // 5. Upload via service client (bypasses RLS for server-side upload; user is still verified via auth)
    const service = createServiceClient();
    const arrayBuffer = await file.arrayBuffer();

    const { error: uploadError } = await service.storage
      .from(BUCKET)
      .upload(storagePath, arrayBuffer, {
        contentType: file.type,
        upsert: true, // overwrite if re-uploading same doc type
      });

    if (uploadError) {
      console.error('[upload/document] storage error:', uploadError);
      return NextResponse.json(
        { error: 'Upload failed. Please try again.' },
        { status: 500 },
      );
    }

    // 6. Generate a short-lived signed URL for previewing the document
    const { data: signedUrlData } = await service.storage
      .from(BUCKET)
      .createSignedUrl(storagePath, 60 * 60); // 1 hour

    return NextResponse.json({
      storagePath,
      storageBucket: BUCKET,
      signedUrl: signedUrlData?.signedUrl ?? null,
      fileName: file.name,
      fileSize: file.size,
      mimeType: file.type,
    });
  } catch (err) {
    console.error('[upload/document] unexpected:', err);
    return NextResponse.json({ error: 'Internal server error.' }, { status: 500 });
  }
}
