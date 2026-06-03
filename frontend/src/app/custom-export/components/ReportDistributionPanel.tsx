"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { getAuthSession, isAdmin } from "@/lib/auth";

interface ReportStat {
  value: string;
  label: string;
}

interface StatusMsg {
  message: string;
  type: "success" | "error" | "info" | "";
}

interface SendResult {
  email: string;
  success: boolean;
  error?: string;
}

export default function ReportDistributionPanel() {
  // Upload state
  const [uploadedHtml, setUploadedHtml] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Report state (populated after S3 upload)
  const [uploading, setUploading] = useState(false);
  const [s3Url, setS3Url] = useState<string | null>(null);
  const [stats, setStats] = useState<ReportStat[]>([]);
  const [reportNumber, setReportNumber] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [executiveSummary, setExecutiveSummary] = useState("");
  const [subject, setSubject] = useState("");
  const [emailHtml, setEmailHtml] = useState<string | null>(null);

  // Recipients / sending
  const [recipients, setRecipients] = useState<string[]>([""]);
  const [sending, setSending] = useState(false);
  const [sendResults, setSendResults] = useState<SendResult[]>([]);
  const [broadcasting, setBroadcasting] = useState(false);

  // Subscribers
  const [subscriberCount, setSubscriberCount] = useState<number | null>(null);

  const [status, setStatus] = useState<StatusMsg>({ message: "", type: "" });
  const [isAdminUser, setIsAdminUser] = useState(false);

  useEffect(() => {
    const session = getAuthSession();
    setIsAdminUser(isAdmin(session?.address));
    api
      .getReportSubscribers()
      .then((d) => setSubscriberCount(d.active))
      .catch(() => {});
  }, []);

  // ----- File handling -----
  const handleFile = useCallback((file: File) => {
    if (!file.name.match(/\.html?$/i)) {
      setStatus({ message: "HTML 파일을 업로드하세요.", type: "error" });
      return;
    }
    setUploadedFileName(file.name);
    setS3Url(null);
    setEmailHtml(null);
    setSendResults([]);
    const reader = new FileReader();
    reader.onload = (e) => {
      setUploadedHtml((e.target?.result as string) || null);
      setStatus({ message: `${file.name} 로드됨. 업로드 준비 완료.`, type: "info" });
    };
    reader.readAsText(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  // ----- Upload to S3 + generate email -----
  const handleUpload = async () => {
    if (!uploadedHtml) return;
    setUploading(true);
    setStatus({ message: "S3 업로드 중...", type: "info" });
    try {
      const data = await api.uploadReportHtml(uploadedHtml);
      setS3Url(data.report_url);
      setStats(data.stats);
      setReportNumber(data.metadata.report_number);
      setDateRange(data.metadata.date_range);
      setExecutiveSummary(data.executive_summary);
      if (!subject) setSubject(data.metadata.title);

      // Build the summary email preview
      const preview = await api.previewReportEmail({
        report_url: data.report_url,
        stats: data.stats,
        summary: data.executive_summary,
        report_number: data.metadata.report_number,
        date_range: data.metadata.date_range,
      });
      setEmailHtml(preview.html);
      setStatus({ message: "S3 업로드 및 이메일 생성 완료!", type: "success" });
    } catch (err: any) {
      setStatus({
        message: `업로드 실패: ${err.response?.data?.error || err.message}`,
        type: "error",
      });
    } finally {
      setUploading(false);
    }
  };

  // ----- Recipients -----
  const updateRecipient = (i: number, value: string) =>
    setRecipients((prev) => prev.map((r, idx) => (idx === i ? value : r)));
  const addRecipient = () => setRecipients((prev) => [...prev, ""]);
  const removeRecipient = (i: number) =>
    setRecipients((prev) => prev.filter((_, idx) => idx !== i));

  // ----- Test send -----
  const handleSendTest = async () => {
    const valid = recipients.map((r) => r.trim()).filter(Boolean);
    if (valid.length === 0 || !emailHtml) return;
    if (!subject) {
      setStatus({ message: "이메일 제목을 입력하세요.", type: "error" });
      return;
    }
    setSending(true);
    setSendResults([]);
    try {
      await api.sendTestReportEmail(valid, subject, emailHtml);
      setSendResults(valid.map((email) => ({ email, success: true })));
      setStatus({ message: `테스트 ${valid.length}건 발송 성공.`, type: "success" });
    } catch (err: any) {
      setSendResults(
        valid.map((email) => ({
          email,
          success: false,
          error: err.response?.data?.error || err.message,
        }))
      );
      setStatus({
        message: `테스트 발송 실패: ${err.response?.data?.error || err.message}`,
        type: "error",
      });
    } finally {
      setSending(false);
    }
  };

  // ----- Broadcast to all -----
  const handleSendAll = async () => {
    if (!emailHtml || !subject) {
      setStatus({ message: "이메일을 먼저 생성하고 제목을 입력하세요.", type: "error" });
      return;
    }
    const count = subscriberCount ?? 0;
    if (!window.confirm(`활성 구독자 ${count}명에게 발송하시겠습니까?`)) return;
    setBroadcasting(true);
    setStatus({ message: "전체 발송 대기열에 추가 중...", type: "info" });
    try {
      const data = await api.sendReportEmailToAll(subject, emailHtml);
      setStatus({
        message: data.message || `${data.queued_count}명에게 발송 대기열 등록됨.`,
        type: "success",
      });
    } catch (err: any) {
      setStatus({
        message: `전체 발송 실패: ${err.response?.data?.error || err.message}`,
        type: "error",
      });
    } finally {
      setBroadcasting(false);
    }
  };

  const statusColor =
    status.type === "success"
      ? "bg-green-50 border-green-200 text-green-700"
      : status.type === "error"
      ? "bg-red-50 border-red-200 text-red-700"
      : "bg-blue-50 border-blue-200 text-blue-700";

  return (
    <div className="flex gap-6 items-start">
      {/* Left column: controls */}
      <div className="w-[420px] flex-shrink-0 space-y-6">
        {/* Upload card */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">
            1. 리포트 HTML 업로드
          </h3>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
              isDragging
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".html,.htm"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            <span className="text-3xl">📄</span>
            <p className="mt-2 text-sm text-gray-600">
              {uploadedFileName || "HTML 파일을 드래그하거나 클릭하여 선택"}
            </p>
          </div>

          <button
            onClick={handleUpload}
            disabled={!uploadedHtml || uploading}
            className="mt-3 w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
          >
            {uploading ? "업로드 중..." : "S3 업로드 & 이메일 생성"}
          </button>

          {s3Url && (
            <p className="mt-2 text-xs text-gray-500 break-all">
              ✅{" "}
              <a
                href={s3Url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline"
              >
                {s3Url}
              </a>
            </p>
          )}
        </div>

        {/* Email controls */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">2. 이메일 설정</h3>
          <label className="block text-xs text-gray-500 mb-1">제목</label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="이메일 제목"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />

          {stats.length > 0 && (
            <div className="mt-3 grid grid-cols-3 gap-2">
              {stats.map((s, i) => (
                <div key={i} className="rounded-md bg-gray-50 p-2 text-center">
                  <div className="text-sm font-bold text-gray-900">{s.value}</div>
                  <div className="text-[10px] uppercase text-gray-500">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Test send */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">
            3. 테스트 발송
          </h3>
          {recipients.map((r, i) => (
            <div key={i} className="mb-2 flex gap-2">
              <input
                type="email"
                value={r}
                onChange={(e) => updateRecipient(i, e.target.value)}
                placeholder="test@example.com"
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
              {recipients.length > 1 && (
                <button
                  onClick={() => removeRecipient(i)}
                  className="rounded-md border border-gray-300 px-2 text-gray-500 hover:bg-gray-50"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <div className="flex gap-2">
            <button
              onClick={addRecipient}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
            >
              + 수신자 추가
            </button>
            <button
              onClick={handleSendTest}
              disabled={!emailHtml || sending}
              className="flex-1 rounded-md bg-gray-800 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-900 disabled:bg-gray-300"
            >
              {sending ? "발송 중..." : "테스트 발송"}
            </button>
          </div>

          {sendResults.length > 0 && (
            <div className="mt-2 space-y-1">
              {sendResults.map((r, i) => (
                <div
                  key={i}
                  className={`text-xs ${
                    r.success ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {r.success ? "✅" : "❌"} {r.email}
                  {r.error ? ` — ${r.error}` : ""}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Broadcast */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-1">4. 전체 발송</h3>
          <p className="text-xs text-gray-500 mb-3">
            활성 구독자:{" "}
            <span className="font-semibold">
              {subscriberCount === null ? "…" : subscriberCount}
            </span>
            명
          </p>
          {isAdminUser ? (
            <button
              onClick={handleSendAll}
              disabled={!emailHtml || broadcasting}
              className="w-full rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:bg-gray-300"
            >
              {broadcasting ? "발송 중..." : "전체 구독자에게 발송"}
            </button>
          ) : (
            <p className="rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-400">
              전체 발송은 관리자만 가능합니다.
            </p>
          )}
        </div>

        {status.message && (
          <div className={`rounded-lg border p-3 text-sm ${statusColor}`}>
            {status.message}
          </div>
        )}
      </div>

      {/* Right column: email preview */}
      <div className="flex-1 min-w-[400px]">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">이메일 미리보기</h3>
          {emailHtml ? (
            <iframe
              title="email-preview"
              srcDoc={emailHtml}
              className="w-full h-[700px] rounded-md border border-gray-200"
            />
          ) : (
            <div className="flex h-[700px] items-center justify-center rounded-md border border-dashed border-gray-200 text-sm text-gray-400">
              HTML 업로드 후 이메일 미리보기가 표시됩니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
