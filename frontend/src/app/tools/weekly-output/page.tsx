"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import apiClient from "@/lib/api";
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  ArrowLeftIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";

// ============================================================
// Types
// ============================================================

interface ScheduleTime {
  day_of_week: string;
  hour: number;
  minute: number;
}

interface Schedule {
  id: string;
  name: string;
  channel_id: string;
  channel_name: string;
  member_ids: string[];
  thread_schedule: ScheduleTime;
  reminder_schedule: ScheduleTime;
  final_schedule: ScheduleTime;
  thread_message: string | null;
  reminder_message: string | null;
  final_message: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface MemberWithSlack {
  id: string;
  name: string;
  slack_user_id: string | null;
}

interface SlackChannel {
  channel_id: string;
  name: string;
}

const DAYS = [
  { value: "mon", label: "Mon" },
  { value: "tue", label: "Tue" },
  { value: "wed", label: "Wed" },
  { value: "thu", label: "Thu" },
  { value: "fri", label: "Fri" },
  { value: "sat", label: "Sat" },
  { value: "sun", label: "Sun" },
];

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55];

function formatTime(st: ScheduleTime): string {
  const dayLabel = DAYS.find((d) => d.value === st.day_of_week)?.label || st.day_of_week;
  return `${dayLabel} ${String(st.hour).padStart(2, "0")}:${String(st.minute).padStart(2, "0")}`;
}

// ============================================================
// Message Presets
// ============================================================

const MESSAGE_PRESETS = {
  weekly_output: {
    label: "Weekly Output",
    thread_message:
      ":memo: *[{week_label}] Weekly Output*\n\nPlease share your work updates for this week in this thread.\nDeadline: *{deadline}*\n\n{mentions}",
    reminder_message:
      ":bell: *Weekly Output Reminder*\n\nYour [{week_label}] Weekly Output hasn't been submitted yet.\nPlease share your work updates in the <{thread_link}|thread> by {deadline}!",
    final_message:
      ":rotating_light: *Weekly Output - Final Notice*\n\nThe [{week_label}] Weekly Output deadline has arrived.\nIf you haven't submitted yet, please post in the <{thread_link}|thread> now!",
  },
} as const;

type PresetKey = keyof typeof MESSAGE_PRESETS | "custom" | "none";

// ============================================================
// Slack mrkdwn to HTML renderer
// ============================================================

const SLACK_EMOJI_MAP: Record<string, string> = {
  ":memo:": "\ud83d\udcdd",
  ":bell:": "\ud83d\udd14",
  ":rotating_light:": "\ud83d\udea8",
  ":warning:": "\u26a0\ufe0f",
  ":white_check_mark:": "\u2705",
  ":x:": "\u274c",
  ":star:": "\u2b50",
  ":rocket:": "\ud83d\ude80",
  ":tada:": "\ud83c\udf89",
  ":calendar:": "\ud83d\udcc6",
  ":clock3:": "\ud83d\udd52",
  ":speech_balloon:": "\ud83d\udcac",
  ":bulb:": "\ud83d\udca1",
  ":fire:": "\ud83d\udd25",
  ":thumbsup:": "\ud83d\udc4d",
  ":eyes:": "\ud83d\udc40",
  ":muscle:": "\ud83d\udcaa",
  ":point_right:": "\ud83d\udc49",
  ":mega:": "\ud83d\udce3",
  ":loudspeaker:": "\ud83d\udce2",
};

function renderSlackMrkdwn(text: string): string {
  let html = text
    // Escape HTML
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Slack emoji codes -> unicode
  for (const [code, emoji] of Object.entries(SLACK_EMOJI_MAP)) {
    html = html.split(code).join(emoji);
  }
  // Remaining emoji codes -> just show the name
  html = html.replace(/:([a-z0-9_+-]+):/g, ":$1:");

  // Slack links: <url|label> -> clickable link
  html = html.replace(
    /&lt;(https?:\/\/[^|&]+)\|([^&]+)&gt;/g,
    '<a href="$1" style="color:#1264a3;text-decoration:none" target="_blank">$2</a>'
  );

  // Bold: *text*
  html = html.replace(/\*([^*\n]+)\*/g, "<strong>$1</strong>");

  // Italic: _text_
  html = html.replace(/\b_([^_\n]+)_\b/g, "<em>$1</em>");

  // Strikethrough: ~text~
  html = html.replace(/~([^~\n]+)~/g, "<del>$1</del>");

  // Code: `text`
  html = html.replace(
    /`([^`\n]+)`/g,
    '<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:12px">$1</code>'
  );

  // Newlines
  html = html.replace(/\n/g, "<br/>");

  return html;
}

// ============================================================
// Main Component
// ============================================================

export default function WeeklyOutputPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [members, setMembers] = useState<MemberWithSlack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    channel_id: "",
    channel_name: "",
    member_ids: [] as string[],
    thread_schedule: { day_of_week: "thu", hour: 17, minute: 0 } as ScheduleTime,
    reminder_schedule: { day_of_week: "fri", hour: 16, minute: 0 } as ScheduleTime,
    final_schedule: { day_of_week: "fri", hour: 17, minute: 0 } as ScheduleTime,
    thread_message: "",
    reminder_message: "",
    final_message: "",
    is_active: true,
  });

  const [memberSearch, setMemberSearch] = useState("");
  const [showCustomMessages, setShowCustomMessages] = useState(false);
  const [messagePreset, setMessagePreset] = useState<PresetKey>("none");
  const [previewTab, setPreviewTab] = useState<"thread" | "reminder" | "final">("thread");
  const [showPreview, setShowPreview] = useState(false);

  // Channel search state
  const [channelSearch, setChannelSearch] = useState("");
  const [channelResults, setChannelResults] = useState<SlackChannel[]>([]);
  const [channelSearching, setChannelSearching] = useState(false);
  const [showChannelDropdown, setShowChannelDropdown] = useState(false);
  const [botMemberStatus, setBotMemberStatus] = useState<
    "unchecked" | "checking" | "member" | "not_member" | "error"
  >("unchecked");
  const channelSearchTimer = useRef<NodeJS.Timeout | null>(null);
  const channelDropdownRef = useRef<HTMLDivElement>(null);

  // Channel membership status for the schedule list (channel_id -> boolean)
  const [channelMemberMap, setChannelMemberMap] = useState<
    Record<string, "checking" | "member" | "not_member" | "error">
  >({});

  // ============================================================
  // Data fetching
  // ============================================================

  const checkChannelMemberships = useCallback(async (scheduleList: Schedule[]) => {
    const uniqueChannels = [...new Set(scheduleList.map((s) => s.channel_id))];
    if (uniqueChannels.length === 0) return;

    // Set all to checking
    setChannelMemberMap((prev) => {
      const next = { ...prev };
      for (const ch of uniqueChannels) next[ch] = "checking";
      return next;
    });

    // Check each channel in parallel
    await Promise.all(
      uniqueChannels.map(async (channelId) => {
        try {
          const resp = await apiClient.get(`/weekly-output/check-channel/${channelId}`);
          setChannelMemberMap((prev) => ({
            ...prev,
            [channelId]:
              resp.ok && resp.is_member ? "member" : resp.ok ? "not_member" : "error",
          }));
        } catch {
          setChannelMemberMap((prev) => ({ ...prev, [channelId]: "error" }));
        }
      })
    );
  }, []);

  const fetchSchedules = useCallback(async () => {
    try {
      const data = await apiClient.getWeeklyOutputSchedules();
      const list = data.schedules || [];
      setSchedules(list);
      checkChannelMemberships(list);
    } catch (err: any) {
      setError(err.message || "Failed to fetch schedules");
    } finally {
      setLoading(false);
    }
  }, [checkChannelMemberships]);

  const fetchMembers = useCallback(async () => {
    try {
      const data = await apiClient.getMembersWithSlack();
      setMembers(data || []);
    } catch (err: any) {
      console.error("Failed to fetch members:", err);
    }
  }, []);

  useEffect(() => {
    fetchSchedules();
    fetchMembers();
  }, [fetchSchedules, fetchMembers]);

  // Close channel dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        channelDropdownRef.current &&
        !channelDropdownRef.current.contains(e.target as Node)
      ) {
        setShowChannelDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ============================================================
  // Channel search
  // ============================================================

  function handleChannelSearchChange(value: string) {
    setChannelSearch(value);
    setShowChannelDropdown(true);

    if (channelSearchTimer.current) clearTimeout(channelSearchTimer.current);

    if (!value.trim()) {
      setChannelResults([]);
      return;
    }

    channelSearchTimer.current = setTimeout(async () => {
      setChannelSearching(true);
      try {
        const response = await apiClient.get(
          "/database/collections/slack_channels/documents",
          {
            limit: 20,
            search: JSON.stringify({
              name: { $regex: value.trim(), $options: "i" },
            }),
          }
        );
        const docs = response?.documents || [];
        setChannelResults(
          docs.map((d: any) => ({
            channel_id: d.channel_id || d.slack_id || d._id,
            name: d.name || "unknown",
          }))
        );
      } catch {
        setChannelResults([]);
      } finally {
        setChannelSearching(false);
      }
    }, 300);
  }

  async function checkBotMembership(channelId: string) {
    setBotMemberStatus("checking");
    try {
      const resp = await apiClient.get(`/weekly-output/check-channel/${channelId}`);
      if (resp.ok && resp.is_member) {
        setBotMemberStatus("member");
      } else if (resp.ok && !resp.is_member) {
        setBotMemberStatus("not_member");
      } else {
        setBotMemberStatus("error");
      }
    } catch {
      setBotMemberStatus("error");
    }
  }

  function selectChannel(ch: SlackChannel) {
    setFormData((p) => ({
      ...p,
      channel_id: ch.channel_id,
      channel_name: ch.name,
    }));
    setChannelSearch("");
    setShowChannelDropdown(false);
    checkBotMembership(ch.channel_id);
  }

  // ============================================================
  // Message preset helpers
  // ============================================================

  function applyPreset(key: PresetKey) {
    setMessagePreset(key);
    if (key === "none") {
      setFormData((p) => ({
        ...p,
        thread_message: "",
        reminder_message: "",
        final_message: "",
      }));
      setShowCustomMessages(false);
    } else if (key === "custom") {
      setShowCustomMessages(true);
    } else {
      const preset = MESSAGE_PRESETS[key];
      setFormData((p) => ({
        ...p,
        thread_message: preset.thread_message,
        reminder_message: preset.reminder_message,
        final_message: preset.final_message,
      }));
      setShowCustomMessages(true);
    }
  }

  // ============================================================
  // Slack preview helpers
  // ============================================================

  function getPreviewText(type: "thread" | "reminder" | "final"): string {
    const raw = formData[`${type}_message`];
    const defaults: Record<string, string> = {
      thread:
        ":memo: *[{week_label}] Weekly Output*\n\nPlease share your work updates for this week in this thread.\nDeadline: *{deadline}*\n\n{mentions}",
      reminder:
        ":bell: *Weekly Output Reminder*\n\nYour [{week_label}] Weekly Output hasn't been submitted yet.\nPlease share your work updates in the <{thread_link}|thread> by {deadline}!",
      final:
        ":rotating_light: *Weekly Output - Final Notice*\n\nThe [{week_label}] Weekly Output deadline has arrived.\nIf you haven't submitted yet, please post in the <{thread_link}|thread> now!",
    };
    const template = raw || defaults[type];

    // Calculate sample week label from thread schedule
    const now = new Date();
    const dayNum: Record<string, number> = {
      mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, sun: 0,
    };
    const threadDay = dayNum[formData.thread_schedule.day_of_week] ?? 4;
    const currentDay = now.getDay();
    const diff = ((currentDay - threadDay) % 7 + 7) % 7;
    const start = new Date(now);
    start.setDate(start.getDate() - diff);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    const weekLabel = `${start.toISOString().slice(0, 10)} ~ ${String(end.getMonth() + 1).padStart(2, "0")}-${String(end.getDate()).padStart(2, "0")}`;

    const fs = formData.final_schedule;
    const fDayLabel = DAYS.find((d) => d.value === fs.day_of_week)?.label || fs.day_of_week;
    const deadlineStr = `${fDayLabel} ${String(fs.hour).padStart(2, "0")}:${String(fs.minute).padStart(2, "0")} KST`;

    // Mentions from selected members
    const selectedNames = members
      .filter((m) => formData.member_ids.includes(m.id))
      .map((m) => `@${m.name}`);
    const mentionsStr = selectedNames.length
      ? selectedNames.join(" ")
      : "@member1 @member2";

    const sampleThreadLink = formData.channel_id
      ? `https://slack.com/archives/${formData.channel_id}/p1234567890123456`
      : "https://slack.com/archives/C0123ABC/p1234567890123456";

    return template
      .replace(/{week_label}/g, weekLabel)
      .replace(/{deadline}/g, deadlineStr)
      .replace(/{mentions}/g, mentionsStr)
      .replace(/{thread_link}/g, sampleThreadLink);
  }

  // ============================================================
  // Modal helpers
  // ============================================================

  function openCreateModal() {
    setEditingSchedule(null);
    setFormData({
      name: "",
      channel_id: "",
      channel_name: "",
      member_ids: [],
      thread_schedule: { day_of_week: "thu", hour: 17, minute: 0 },
      reminder_schedule: { day_of_week: "fri", hour: 16, minute: 0 },
      final_schedule: { day_of_week: "fri", hour: 17, minute: 0 },
      thread_message: "",
      reminder_message: "",
      final_message: "",
      is_active: true,
    });
    setMemberSearch("");
    setChannelSearch("");
    setShowCustomMessages(false);
    setMessagePreset("none");
    setShowPreview(false);
    setBotMemberStatus("unchecked");
    setShowModal(true);
  }

  function openEditModal(schedule: Schedule) {
    setEditingSchedule(schedule);
    setFormData({
      name: schedule.name,
      channel_id: schedule.channel_id,
      channel_name: schedule.channel_name,
      member_ids: [...schedule.member_ids],
      thread_schedule: { ...schedule.thread_schedule },
      reminder_schedule: { ...schedule.reminder_schedule },
      final_schedule: { ...schedule.final_schedule },
      thread_message: schedule.thread_message || "",
      reminder_message: schedule.reminder_message || "",
      final_message: schedule.final_message || "",
      is_active: schedule.is_active,
    });
    setMemberSearch("");
    setChannelSearch("");
    const hasCustom = !!(schedule.thread_message || schedule.reminder_message || schedule.final_message);
    setShowCustomMessages(hasCustom);
    // Detect if it matches a preset
    if (hasCustom) {
      const woPreset = MESSAGE_PRESETS.weekly_output;
      if (
        schedule.thread_message === woPreset.thread_message &&
        schedule.reminder_message === woPreset.reminder_message &&
        schedule.final_message === woPreset.final_message
      ) {
        setMessagePreset("weekly_output");
      } else {
        setMessagePreset("custom");
      }
    } else {
      setMessagePreset("none");
    }
    setShowPreview(false);
    setBotMemberStatus("unchecked");
    if (schedule.channel_id) {
      checkBotMembership(schedule.channel_id);
    }
    setShowModal(true);
  }

  // ============================================================
  // CRUD handlers
  // ============================================================

  async function handleSave() {
    if (!formData.name.trim() || !formData.channel_id.trim()) {
      setError("Name and Channel are required");
      return;
    }

    setSaving(true);
    setError(null);

    const payload = {
      name: formData.name.trim(),
      channel_id: formData.channel_id.trim(),
      channel_name: formData.channel_name.trim(),
      member_ids: formData.member_ids,
      thread_schedule: formData.thread_schedule,
      reminder_schedule: formData.reminder_schedule,
      final_schedule: formData.final_schedule,
      thread_message: formData.thread_message.trim() || null,
      reminder_message: formData.reminder_message.trim() || null,
      final_message: formData.final_message.trim() || null,
      is_active: formData.is_active,
    };

    try {
      if (editingSchedule) {
        await apiClient.updateWeeklyOutputSchedule(editingSchedule.id, payload);
      } else {
        await apiClient.createWeeklyOutputSchedule(payload);
      }
      setShowModal(false);
      await fetchSchedules();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this schedule?")) return;
    setDeleting(id);
    try {
      await apiClient.deleteWeeklyOutputSchedule(id);
      await fetchSchedules();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to delete");
    } finally {
      setDeleting(null);
    }
  }

  async function handleToggle(schedule: Schedule) {
    try {
      await apiClient.updateWeeklyOutputSchedule(schedule.id, {
        is_active: !schedule.is_active,
      });
      await fetchSchedules();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to toggle");
    }
  }

  // ============================================================
  // Member selection helpers
  // ============================================================

  const filteredMembers = members.filter((m) =>
    m.name.toLowerCase().includes(memberSearch.toLowerCase())
  );

  function toggleMember(memberId: string) {
    setFormData((prev) => ({
      ...prev,
      member_ids: prev.member_ids.includes(memberId)
        ? prev.member_ids.filter((id) => id !== memberId)
        : [...prev.member_ids, memberId],
    }));
  }

  function selectAllFiltered() {
    const filteredIds = filteredMembers.map((m) => m.id);
    setFormData((prev) => ({
      ...prev,
      member_ids: [...new Set([...prev.member_ids, ...filteredIds])],
    }));
  }

  function deselectAll() {
    setFormData((prev) => ({ ...prev, member_ids: [] }));
  }

  // ============================================================
  // Schedule time editor component
  // ============================================================

  function ScheduleTimeEditor({
    label,
    value,
    onChange,
  }: {
    label: string;
    value: ScheduleTime;
    onChange: (v: ScheduleTime) => void;
  }) {
    return (
      <div className="flex items-center space-x-2">
        <span className="text-sm font-medium text-gray-700 w-20">{label}</span>
        <select
          value={value.day_of_week}
          onChange={(e) => onChange({ ...value, day_of_week: e.target.value })}
          className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
        >
          {DAYS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
        <select
          value={value.hour}
          onChange={(e) => onChange({ ...value, hour: parseInt(e.target.value) })}
          className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
        >
          {HOURS.map((h) => (
            <option key={h} value={h}>
              {String(h).padStart(2, "0")}
            </option>
          ))}
        </select>
        <span className="text-gray-500">:</span>
        <select
          value={value.minute}
          onChange={(e) => onChange({ ...value, minute: parseInt(e.target.value) })}
          className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
        >
          {MINUTES.map((m) => (
            <option key={m} value={m}>
              {String(m).padStart(2, "0")}
            </option>
          ))}
        </select>
      </div>
    );
  }

  // ============================================================
  // Render
  // ============================================================

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <Link
            href="/tools"
            className="text-gray-500 hover:text-gray-700 transition-colors"
          >
            <ArrowLeftIcon className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">
            Weekly Output Schedules
          </h1>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          <PlusIcon className="h-4 w-4 mr-2" />
          New Schedule
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-500 hover:text-red-700"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading schedules...</div>
      ) : schedules.length === 0 ? (
        <div className="text-center py-12 border-2 border-dashed border-gray-300 rounded-lg">
          <p className="text-gray-500 mb-4">No schedules yet.</p>
          <button
            onClick={openCreateModal}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Create your first schedule
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto bg-white rounded-lg shadow">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Channel
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Members
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Schedule
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {schedules.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {s.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    #{s.channel_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {s.member_ids.length} member{s.member_ids.length !== 1 ? "s" : ""}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    <div className="space-y-0.5">
                      <div>
                        <span className="text-gray-400 text-xs">Thread:</span>{" "}
                        {formatTime(s.thread_schedule)}
                      </div>
                      <div>
                        <span className="text-gray-400 text-xs">Reminder:</span>{" "}
                        {formatTime(s.reminder_schedule)}
                      </div>
                      <div>
                        <span className="text-gray-400 text-xs">Final:</span>{" "}
                        {formatTime(s.final_schedule)}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {channelMemberMap[s.channel_id] === "not_member" ? (
                      <div className="space-y-1">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                          Bot not invited
                        </span>
                        <p className="text-[10px] text-amber-600 leading-tight">
                          /invite @All-Thing-Eye Scheduler
                        </p>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleToggle(s)}
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                          s.is_active
                            ? "bg-green-100 text-green-800 hover:bg-green-200"
                            : "bg-gray-100 text-gray-800 hover:bg-gray-200"
                        }`}
                      >
                        {channelMemberMap[s.channel_id] === "checking"
                          ? "Checking..."
                          : s.is_active
                          ? "Active"
                          : "Inactive"}
                      </button>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <button
                      onClick={() => openEditModal(s)}
                      className="text-blue-600 hover:text-blue-800 mr-3"
                      title="Edit"
                    >
                      <PencilIcon className="h-4 w-4 inline" />
                    </button>
                    <button
                      onClick={() => handleDelete(s.id)}
                      disabled={deleting === s.id}
                      className="text-red-600 hover:text-red-800 disabled:opacity-50"
                      title="Delete"
                    >
                      <TrashIcon className="h-4 w-4 inline" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div
              className="fixed inset-0 bg-black/40"
              onClick={() => setShowModal(false)}
            />
            <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              {/* Modal header */}
              <div className="flex items-center justify-between px-6 py-4 border-b">
                <h2 className="text-lg font-semibold text-gray-900">
                  {editingSchedule ? "Edit Schedule" : "New Schedule"}
                </h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>

              {/* Modal body */}
              <div className="px-6 py-4 space-y-6">
                {/* Basic info */}
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                    Basic Info
                  </h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Name *
                    </label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) =>
                        setFormData((p) => ({ ...p, name: e.target.value }))
                      }
                      placeholder="e.g. Project OOO Weekly Output"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  {/* Channel selector */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Channel *
                    </label>
                    {formData.channel_id ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm bg-gray-50 flex items-center justify-between">
                            <span>
                              <span className="text-gray-400">#</span>{" "}
                              <span className="font-medium text-gray-900">
                                {formData.channel_name || formData.channel_id}
                              </span>
                              <span className="ml-2 text-xs text-gray-400">
                                {formData.channel_id}
                              </span>
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                setFormData((p) => ({
                                  ...p,
                                  channel_id: "",
                                  channel_name: "",
                                }));
                                setChannelSearch("");
                                setBotMemberStatus("unchecked");
                              }}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              <XMarkIcon className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                        {botMemberStatus === "checking" && (
                          <p className="text-xs text-gray-400 flex items-center gap-1">
                            <span className="inline-block h-3 w-3 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
                            Checking bot membership...
                          </p>
                        )}
                        {botMemberStatus === "member" && (
                          <p className="text-xs text-green-600">
                            Bot is a member of this channel
                          </p>
                        )}
                        {botMemberStatus === "not_member" && (
                          <div className="p-2 bg-amber-50 border border-amber-200 rounded-md">
                            <p className="text-xs text-amber-800 font-medium">
                              Bot is not in this channel
                            </p>
                            <p className="text-xs text-amber-600 mt-0.5">
                              Run <code className="bg-amber-100 px-1 rounded">/invite @All-Thing-Eye Scheduler</code> in{" "}
                              <strong>#{formData.channel_name || formData.channel_id}</strong> first
                            </p>
                          </div>
                        )}
                        {botMemberStatus === "error" && (
                          <p className="text-xs text-gray-400">
                            Could not verify bot membership
                          </p>
                        )}
                      </div>
                    ) : (
                      <div className="relative" ref={channelDropdownRef}>
                        <MagnifyingGlassIcon className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                        <input
                          type="text"
                          value={channelSearch}
                          onChange={(e) => handleChannelSearchChange(e.target.value)}
                          onFocus={() => channelSearch && setShowChannelDropdown(true)}
                          placeholder="Search by channel name..."
                          className="w-full border border-gray-300 rounded-md pl-9 pr-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                        />
                        {channelSearching && (
                          <div className="absolute right-3 top-2.5">
                            <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                          </div>
                        )}
                        {showChannelDropdown && channelSearch && (
                          <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
                            {channelResults.length === 0 ? (
                              <div className="px-3 py-2 text-sm text-gray-500">
                                {channelSearching
                                  ? "Searching..."
                                  : "No channels found"}
                              </div>
                            ) : (
                              channelResults.map((ch) => (
                                <button
                                  key={ch.channel_id}
                                  type="button"
                                  onClick={() => selectChannel(ch)}
                                  className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 flex items-center justify-between border-b border-gray-50 last:border-0"
                                >
                                  <span>
                                    <span className="text-gray-400">#</span>{" "}
                                    <span className="font-medium">{ch.name}</span>
                                  </span>
                                  <span className="text-xs text-gray-400">
                                    {ch.channel_id}
                                  </span>
                                </button>
                              ))
                            )}
                          </div>
                        )}
                        <p className="mt-1 text-xs text-gray-400">
                          Or enter Channel ID directly:{" "}
                          <button
                            type="button"
                            onClick={() => {
                              const id = prompt("Enter Slack Channel ID (e.g. C0123ABCDEF):");
                              if (id?.trim()) {
                                setFormData((p) => ({
                                  ...p,
                                  channel_id: id.trim(),
                                  channel_name: "",
                                }));
                                checkBotMembership(id.trim());
                              }
                            }}
                            className="text-blue-600 hover:text-blue-800 underline"
                          >
                            manual input
                          </button>
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Member selection */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                      Members ({formData.member_ids.length} selected)
                    </h3>
                    <div className="space-x-2">
                      <button
                        onClick={selectAllFiltered}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        Select all
                      </button>
                      <button
                        onClick={deselectAll}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="relative">
                    <MagnifyingGlassIcon className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                    <input
                      type="text"
                      value={memberSearch}
                      onChange={(e) => setMemberSearch(e.target.value)}
                      placeholder="Search members..."
                      className="w-full border border-gray-300 rounded-md pl-9 pr-3 py-2 text-sm"
                    />
                  </div>
                  {/* Selected members chips */}
                  {formData.member_ids.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {members
                        .filter((m) => formData.member_ids.includes(m.id))
                        .map((m) => (
                          <span
                            key={m.id}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"
                          >
                            {m.name}
                            <button
                              type="button"
                              onClick={() => toggleMember(m.id)}
                              className="text-blue-400 hover:text-blue-600"
                            >
                              <XMarkIcon className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                    </div>
                  )}
                  <div className="border border-gray-200 rounded-md max-h-48 overflow-y-auto">
                    {filteredMembers.length === 0 ? (
                      <div className="p-3 text-sm text-gray-500 text-center">
                        No members found
                      </div>
                    ) : (
                      filteredMembers.map((m) => (
                        <label
                          key={m.id}
                          className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0"
                        >
                          <input
                            type="checkbox"
                            checked={formData.member_ids.includes(m.id)}
                            onChange={() => toggleMember(m.id)}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-3"
                          />
                          <span className="text-sm text-gray-900">{m.name}</span>
                          {m.slack_user_id ? (
                            <span className="ml-auto text-xs text-green-600">
                              Slack linked
                            </span>
                          ) : (
                            <span className="ml-auto text-xs text-gray-400">
                              No Slack ID
                            </span>
                          )}
                        </label>
                      ))
                    )}
                  </div>
                </div>

                {/* Schedule times */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                    Schedule (KST)
                  </h3>
                  <div className="space-y-2">
                    <ScheduleTimeEditor
                      label="Thread"
                      value={formData.thread_schedule}
                      onChange={(v) =>
                        setFormData((p) => ({ ...p, thread_schedule: v }))
                      }
                    />
                    <ScheduleTimeEditor
                      label="Reminder"
                      value={formData.reminder_schedule}
                      onChange={(v) =>
                        setFormData((p) => ({ ...p, reminder_schedule: v }))
                      }
                    />
                    <ScheduleTimeEditor
                      label="Final"
                      value={formData.final_schedule}
                      onChange={(v) =>
                        setFormData((p) => ({ ...p, final_schedule: v }))
                      }
                    />
                  </div>
                </div>

                {/* Custom messages with preset selector */}
                <div>
                  <button
                    onClick={() => setShowCustomMessages(!showCustomMessages)}
                    className="flex items-center text-sm font-semibold text-gray-700 uppercase tracking-wide hover:text-gray-900"
                  >
                    {showCustomMessages ? (
                      <ChevronUpIcon className="h-4 w-4 mr-1" />
                    ) : (
                      <ChevronDownIcon className="h-4 w-4 mr-1" />
                    )}
                    Custom Messages (optional)
                  </button>
                  {showCustomMessages && (
                    <div className="mt-3 space-y-4">
                      {/* Preset selector */}
                      <div>
                        <label className="block text-sm text-gray-600 mb-2">
                          Message Preset
                        </label>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => applyPreset("none")}
                            className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
                              messagePreset === "none"
                                ? "bg-gray-800 text-white border-gray-800"
                                : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
                            }`}
                          >
                            Default (no custom)
                          </button>
                          <button
                            type="button"
                            onClick={() => applyPreset("weekly_output")}
                            className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
                              messagePreset === "weekly_output"
                                ? "bg-blue-600 text-white border-blue-600"
                                : "bg-white text-blue-600 border-blue-300 hover:border-blue-400"
                            }`}
                          >
                            Weekly Output
                          </button>
                          <button
                            type="button"
                            onClick={() => applyPreset("custom")}
                            className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
                              messagePreset === "custom"
                                ? "bg-purple-600 text-white border-purple-600"
                                : "bg-white text-purple-600 border-purple-300 hover:border-purple-400"
                            }`}
                          >
                            Custom
                          </button>
                        </div>
                      </div>

                      {messagePreset !== "none" && (
                        <>
                          <p className="text-xs text-gray-500">
                            Variables:{" "}
                            <code className="bg-gray-100 px-1 rounded">
                              {"{week_label}"}
                            </code>
                            ,{" "}
                            <code className="bg-gray-100 px-1 rounded">
                              {"{mentions}"}
                            </code>
                            ,{" "}
                            <code className="bg-gray-100 px-1 rounded">
                              {"{deadline}"}
                            </code>
                            ,{" "}
                            <code className="bg-gray-100 px-1 rounded">
                              {"{thread_link}"}
                            </code>
                          </p>
                          <p className="text-xs text-gray-400">
                            Slack link format:{" "}
                            <code className="bg-gray-100 px-1 rounded">
                              {"<{thread_link}|thread>"}
                            </code>
                          </p>
                          <div>
                            <label className="block text-sm text-gray-600 mb-1">
                              Thread message
                            </label>
                            <textarea
                              value={formData.thread_message}
                              onChange={(e) =>
                                setFormData((p) => ({
                                  ...p,
                                  thread_message: e.target.value,
                                }))
                              }
                              rows={3}
                              placeholder=":memo: *[{week_label}] Weekly Output*\nPlease share your work updates..."
                              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-600 mb-1">
                              Reminder message
                            </label>
                            <textarea
                              value={formData.reminder_message}
                              onChange={(e) =>
                                setFormData((p) => ({
                                  ...p,
                                  reminder_message: e.target.value,
                                }))
                              }
                              rows={3}
                              placeholder=":bell: *Weekly Output Reminder*\nYour [{week_label}] submission is pending..."
                              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-600 mb-1">
                              Final message
                            </label>
                            <textarea
                              value={formData.final_message}
                              onChange={(e) =>
                                setFormData((p) => ({
                                  ...p,
                                  final_message: e.target.value,
                                }))
                              }
                              rows={3}
                              placeholder=":rotating_light: *Weekly Output - Final Notice*\nThe deadline has arrived..."
                              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
                            />
                          </div>

                          {/* Preview toggle */}
                          <button
                            type="button"
                            onClick={() => setShowPreview(!showPreview)}
                            className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium"
                          >
                            <EyeIcon className="h-4 w-4" />
                            {showPreview ? "Hide Preview" : "Slack Preview"}
                          </button>

                          {showPreview && (
                            <div className="border border-gray-200 rounded-lg overflow-hidden">
                              {/* Preview tab bar */}
                              <div className="flex border-b border-gray-200 bg-gray-50">
                                {(["thread", "reminder", "final"] as const).map(
                                  (tab) => (
                                    <button
                                      key={tab}
                                      type="button"
                                      onClick={() => setPreviewTab(tab)}
                                      className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                                        previewTab === tab
                                          ? "text-blue-600 border-b-2 border-blue-600 bg-white"
                                          : "text-gray-500 hover:text-gray-700"
                                      }`}
                                    >
                                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                                    </button>
                                  )
                                )}
                              </div>
                              {/* Slack-style message preview */}
                              <div className="p-4 bg-white">
                                <div className="flex gap-3">
                                  {/* Bot avatar */}
                                  <div className="flex-shrink-0 w-9 h-9 rounded-md bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
                                    ATI
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    {/* Bot name + timestamp */}
                                    <div className="flex items-baseline gap-2 mb-1">
                                      <span className="font-bold text-sm text-gray-900">
                                        All-Thing-Eye Scheduler
                                      </span>
                                      <span className="text-xs text-gray-400">
                                        {new Date().toLocaleTimeString("en-US", {
                                          hour: "numeric",
                                          minute: "2-digit",
                                          hour12: true,
                                        })}
                                      </span>
                                    </div>
                                    {/* Message content */}
                                    <div
                                      className="text-sm text-gray-800 leading-relaxed [&_strong]:font-bold [&_em]:italic [&_del]:line-through"
                                      dangerouslySetInnerHTML={{
                                        __html: renderSlackMrkdwn(
                                          getPreviewText(previewTab)
                                        ),
                                      }}
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>

                {/* Active toggle */}
                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) =>
                      setFormData((p) => ({ ...p, is_active: e.target.checked }))
                    }
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">Active</span>
                </label>
              </div>

              {/* Modal footer */}
              <div className="flex justify-end space-x-3 px-6 py-4 border-t bg-gray-50">
                <button
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving
                    ? "Saving..."
                    : editingSchedule
                    ? "Update"
                    : "Create"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
