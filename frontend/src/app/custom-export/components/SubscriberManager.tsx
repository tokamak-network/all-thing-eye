"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Subscriber {
  id: string;
  email: string;
  name?: string;
  source?: string;
  status: string;
}

interface Props {
  isAdmin: boolean;
  onCountChange?: (activeCount: number) => void;
}

export default function SubscriberManager({ isAdmin, onCountChange }: Props) {
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [total, setTotal] = useState(0);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.getReportSubscribers();
      setSubscribers(d.subscribers);
      setTotal(d.total);
      setActive(d.active);
      onCountChange?.(d.active);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || "불러오기 실패");
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async () => {
    const email = newEmail.trim().toLowerCase();
    if (!email) return;
    setBusy(true);
    setError(null);
    try {
      await api.addReportSubscriber(email, newName.trim() || undefined);
      setNewEmail("");
      setNewName("");
      await load();
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || "추가 실패");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: string, email: string) => {
    if (!window.confirm(`${email} 구독을 취소(unsubscribe)하시겠습니까?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteReportSubscriber(id);
      await load();
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || "삭제 실패");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-700">5. 구독자 관리</h3>
        <span className="text-xs text-gray-500">
          active <span className="font-semibold text-gray-800">{active}</span> / {total}
        </span>
      </div>

      {/* Add form */}
      <div className="flex gap-2 mb-2">
        <input
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && isAdmin && !busy && handleAdd()}
          placeholder="email@example.com"
          disabled={!isAdmin || busy}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50"
        />
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="이름(선택)"
          disabled={!isAdmin || busy}
          className="w-24 rounded-md border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50"
        />
        <button
          onClick={handleAdd}
          disabled={!isAdmin || busy || !newEmail.trim()}
          className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
        >
          추가
        </button>
      </div>

      {!isAdmin && (
        <p className="mb-2 text-xs text-gray-400">구독자 추가/삭제는 관리자만 가능합니다.</p>
      )}
      {error && <p className="mb-2 text-xs text-red-600">{error}</p>}

      {/* List */}
      <div className="max-h-64 overflow-y-auto rounded-md border border-gray-100">
        {loading ? (
          <p className="p-3 text-xs text-gray-400">불러오는 중…</p>
        ) : subscribers.length === 0 ? (
          <p className="p-3 text-xs text-gray-400">구독자가 없습니다.</p>
        ) : (
          subscribers.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between border-b border-gray-50 px-3 py-1.5 last:border-0"
            >
              <div className="min-w-0">
                <span className="block truncate text-xs text-gray-800">{s.email}</span>
                <span className="text-[10px] text-gray-400">
                  {s.source || "-"}
                  {s.status !== "active" ? ` · ${s.status}` : ""}
                </span>
              </div>
              {isAdmin && s.status === "active" && (
                <button
                  onClick={() => handleDelete(s.id, s.email)}
                  disabled={busy}
                  className="ml-2 shrink-0 rounded border border-gray-200 px-2 py-0.5 text-[10px] text-gray-500 hover:bg-red-50 hover:text-red-600"
                >
                  구독취소
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
