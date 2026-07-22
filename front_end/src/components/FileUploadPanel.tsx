import { ChangeEvent, useMemo, useState } from "react";

import { API_BASE_URL } from "../api/client";

type FileUploadPanelProps = {
  baseUploadUrl?: string;
  uploadedFilePath?: string | null;
  onFileSelect?: (file: File | null) => void;
};

const DEFAULT_BASE_UPLOAD_URL = import.meta.env.VITE_BASE_UPLOAD_URL ?? "/uploads";

function normalizeFileUrl(baseUploadUrl: string, uploadedFilePath: string): string {
  if (/^https?:\/\//i.test(uploadedFilePath)) {
    return uploadedFilePath;
  }

  const normalizedBasePath = `/${baseUploadUrl.replace(/^\/+|\/+$/g, "")}`;
  const normalizedFilePath = uploadedFilePath.replace(/^\/+/, "");
  return `${API_BASE_URL}${normalizedBasePath}/${normalizedFilePath}`;
}

export function FileUploadPanel({
  baseUploadUrl = DEFAULT_BASE_UPLOAD_URL,
  uploadedFilePath = null,
  onFileSelect,
}: FileUploadPanelProps) {
  const [selectedFileName, setSelectedFileName] = useState<string>("");

  const fileUrl = useMemo(() => {
    if (!uploadedFilePath) {
      return null;
    }
    return normalizeFileUrl(baseUploadUrl, uploadedFilePath);
  }, [baseUploadUrl, uploadedFilePath]);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFileName(file?.name ?? "");
    onFileSelect?.(file);
  };

  return (
    <section>
      <h2>File Upload</h2>
      <input type="file" accept="image/*" onChange={handleChange} />
      {selectedFileName ? <p>selected: {selectedFileName}</p> : <p>selected: none</p>}

      {fileUrl ? (
        <div>
          <img
            src={fileUrl}
            alt="uploaded preview"
            style={{ maxWidth: 320, display: "block", marginTop: 12 }}
          />
          <a href={fileUrl} download style={{ display: "inline-block", marginTop: 8 }}>
            Download uploaded file
          </a>
        </div>
      ) : (
        <p>uploaded file path is not set.</p>
      )}
    </section>
  );
}
