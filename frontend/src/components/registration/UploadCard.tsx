'use client';

import React, { useRef, useState } from 'react';
import { motion } from 'motion/react';
import { UploadedDocument } from '../../types/registration';
import {
  Upload,
  FileCheck,
  FileText,
  Trash2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Eye,
  File,
} from 'lucide-react';

interface UploadCardProps {
  docType: string;
  title: string;
  description: string;
  required: boolean;
  allowedTypes: string;
  document: UploadedDocument | null;
  onUpload: (docType: string, file: File) => void;
  onRemove: (docType: string) => void;
}

export const UploadCard: React.FC<UploadCardProps> = ({
  docType,
  title,
  description,
  required,
  allowedTypes,
  document,
  onUpload,
  onRemove,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(docType, e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onUpload(docType, e.dataTransfer.files[0]);
    }
  };

  const triggerSelect = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="bg-white rounded-2xl border border-[#D6E8DE] p-5 sm:p-6 shadow-xs hover:border-[#0F766E]/40 transition-all">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        onChange={handleFileChange}
        className="hidden"
      />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              document?.status === 'completed'
                ? 'bg-[#ECFDF5] text-[#16A34A]'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            {document?.status === 'completed' ? (
              <FileCheck className="w-5 h-5 text-[#16A34A]" />
            ) : (
              <FileText className="w-5 h-5" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-extrabold text-[#0F172A]">{title}</h4>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  required
                    ? 'bg-amber-50 text-[#F59E0B] border border-amber-200'
                    : 'bg-slate-100 text-slate-500'
                }`}
              >
                {required ? 'Required' : 'Optional'}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{description}</p>
          </div>
        </div>

        <span className="text-[11px] font-medium text-slate-400">
          Format: {allowedTypes}
        </span>
      </div>

      {/* Upload Zone or Uploaded State */}
      {!document ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={triggerSelect}
          className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all duration-200 ${
            isDragOver
              ? 'border-[#0F766E] bg-[#ECFDF5]/80 scale-[1.01]'
              : 'border-[#D6E8DE] bg-[#FAFAF8] hover:border-[#0F766E]/50 hover:bg-[#ECFDF5]/40'
          }`}
        >
          <div className="w-10 h-10 rounded-full bg-white text-[#0F766E] flex items-center justify-center mx-auto mb-2 shadow-xs border border-[#D6E8DE]">
            <Upload className="w-5 h-5" />
          </div>
          <p className="text-xs font-bold text-[#0F172A]">
            Drag & drop file here or <span className="text-[#0F766E] underline">browse</span>
          </p>
          <p className="text-[10px] text-slate-400 mt-1">Maximum file size: 10MB</p>
        </div>
      ) : (
        <div className="bg-[#FAFAF8] border border-[#D6E8DE] rounded-xl p-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-white border border-[#D6E8DE] flex items-center justify-center shrink-0">
                <File className="w-4 h-4 text-[#0F766E]" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-[#0F172A] truncate">
                  {document.fileName}
                </p>
                <span className="text-[10px] font-semibold text-slate-400 block">
                  {document.fileSize} • {document.fileType}
                </span>
              </div>
            </div>

            {/* Status & Actions */}
            <div className="flex items-center gap-2 shrink-0">
              {document.status === 'completed' && (
                <>
                  <button
                    onClick={() => setShowPreviewModal(true)}
                    className="p-1.5 text-slate-500 hover:text-[#0F766E] hover:bg-emerald-100/60 rounded-lg transition-colors cursor-pointer"
                    title="Preview file"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={triggerSelect}
                    className="p-1.5 text-slate-500 hover:text-[#0F766E] hover:bg-emerald-100/60 rounded-lg transition-colors cursor-pointer"
                    title="Replace file"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onRemove(docType)}
                    className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
                    title="Remove file"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Upload Progress Bar */}
          <div className="mt-2">
            <div className="flex items-center justify-between text-[11px] font-semibold mb-1">
              <span className="text-slate-500">
                {document.status === 'uploading'
                  ? 'Uploading & verifying document...'
                  : 'Document Verified'}
              </span>
              <span className="text-[#0F766E] font-bold">
                {document.uploadProgress}%
              </span>
            </div>
            <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <motion.div
                className={`h-full ${
                  document.status === 'completed' ? 'bg-[#16A34A]' : 'bg-[#0F766E]'
                }`}
                initial={{ width: '0%' }}
                animate={{ width: `${document.uploadProgress}%` }}
                transition={{ duration: 0.2 }}
              />
            </div>
          </div>

          {document.status === 'completed' && (
            <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-bold text-[#16A34A]">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Ready for compliance audit</span>
            </div>
          )}
        </div>
      )}

      {/* File Preview Modal Mockup */}
      {showPreviewModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 border border-[#D6E8DE] shadow-2xl">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200">
              <h4 className="font-bold text-sm text-[#0F172A]">{title} Preview</h4>
              <button
                onClick={() => setShowPreviewModal(false)}
                className="text-slate-400 hover:text-slate-700 font-bold text-lg"
              >
                ✕
              </button>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-8 text-center min-h-[200px] flex flex-col items-center justify-center">
              {document?.previewUrl ? (
                <img
                  src={document.previewUrl}
                  alt="Preview"
                  className="max-h-40 rounded border object-contain mb-3"
                  onError={(e) => {
                    // Fallback to file icon if object URL preview cannot render image
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
              ) : null}
              <FileText className="w-12 h-12 text-[#0F766E] mb-2" />
              <p className="text-xs font-bold text-[#0F172A]">{document?.fileName}</p>
              <span className="text-[11px] text-slate-500 mt-1">
                Verified Document • CPCB Audit Compliant
              </span>
            </div>
            <button
              onClick={() => setShowPreviewModal(false)}
              className="mt-5 w-full py-2.5 bg-[#0F766E] text-white rounded-xl text-xs font-bold"
            >
              Close Preview
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
