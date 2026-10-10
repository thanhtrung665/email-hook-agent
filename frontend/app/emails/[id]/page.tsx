'use client';

import { useEffect, use, useState } from 'react';
import Link from 'next/link';
import {
    ArrowLeft, Building2, Phone, Mail, User,
    Paperclip, CheckSquare,
    AlertCircle, FileText, Download, Check, Loader2,
} from 'lucide-react';
import { LABELS } from '@/lib/data';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api';

// ---------- Types khớp với API GET /api/emails/{id} ----------
interface ThreadItem {
    id_email: string;
    subject: string;
    sender_name: string | null;
    sender_email: string | null;
    sent_at: string | null;
    received_at: string | null;
    body_clean: string | null;
    content_summarized: string;
    has_attachments: boolean;
}
interface EmailDetail {
    id_email: string;
    id_mailbox: string;
    metadata: { subject: string; received_at: string; language: string | null; status: string };
    contact: {
        id_sender: string | null;
        name: string | null;
        email: string | null;
        cc_emails: string[];
        bcc_emails: string[];
        company: string | null;
        phone: string | null;
        is_internal: boolean;
        is_known_customer: boolean;
    };
    content: {
        message_id: string;
        thread_id: string | null;
        in_reply_to: string | null;
        body_clean: string | null;
        body_full: string | null;
        content_summarized: string;
        received_at: string;
        has_attachments: boolean;
    };
    ai_analysis: {
        tldr: string;
        key_points: { action_items?: { task: string; due_date?: string | null }[]; sentiment?: string };
        security: { risk_level?: string; is_phishing?: boolean; is_spam?: boolean; flags?: string[] } | null;
    };
    attachments: {
        id: string;
        file_name: string;
        size_bytes: number;
        mime_type: string | null;
        process_status: string;
        storage_key: string;
        is_inline: boolean;
    }[];
    assigned_labels: { label_name: string; source: string }[];
}

// ---------- Helpers ----------
function formatBytes(n: number): string {
    if (!n) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(Math.floor(Math.log(n) / Math.log(k)), sizes.length - 1);
    return `${parseFloat((n / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(iso: string | null | undefined): string {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('vi-VN', {
            hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric',
        });
    } catch {
        return iso;
    }
}

function Mono({ children }: { children: React.ReactNode }) {
    return <span className="font-mono text-[13px] break-all">{children}</span>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3 py-2 border-b border-slate-100 last:border-0">
            <span className="sm:w-36 shrink-0 text-xs font-semibold uppercase tracking-wider text-slate-400 pt-0.5">{label}</span>
            <div className="text-sm text-slate-800 flex-1 min-w-0">{children}</div>
        </div>
    );
}

function Badge({ ok, text }: { ok: boolean; text: string }) {
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${ok ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
            {text}
        </span>
    );
}

// Attachment inline viewer: PDF iframe, ảnh preview, docx/xlsx preview bảng, còn lại chỉ download
function AttachmentViewer({ att }: { att: EmailDetail['attachments'][number] }) {
    const url = `${API_URL}/emails/attachments/${att.id}`;
    const nameLower = att.file_name.toLowerCase();
    const isPdf = att.mime_type === 'application/pdf' || nameLower.endsWith('.pdf');
    const isImage = (att.mime_type?.startsWith('image/') ?? false) || /\.(png|jpe?g|gif|bmp|webp|svg)$/i.test(att.file_name);
    const isDocLike = nameLower.endsWith('.docx') || nameLower.endsWith('.doc') || nameLower.endsWith('.xlsx') || nameLower.endsWith('.xls') || nameLower.endsWith('.pptx');

    return (
        <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="bg-slate-800 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-white min-w-0">
                    <FileText className="h-5 w-5 text-blue-400 shrink-0" />
                    <span className="font-semibold text-sm truncate">{att.file_name}</span>
                    <span className="text-xs text-slate-400 ml-2 shrink-0">({formatBytes(att.size_bytes)})</span>
                </div>
                <a href={url} download={att.file_name} className="text-slate-300 hover:text-white flex items-center gap-2 text-xs font-medium bg-slate-700 px-3 py-1.5 rounded-md transition shrink-0">
                    <Download className="h-3 w-3" /> Tải gốc
                </a>
            </div>
            {isPdf && (
                <div className="bg-slate-100">
                    <iframe src={url} className="w-full h-[500px]" title={`Xem ${att.file_name}`} />
                </div>
            )}
            {isImage && !isPdf && (
                <div className="bg-slate-100">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={url} alt={att.file_name} className="max-h-[500px] mx-auto object-contain" />
                </div>
            )}
            {isDocLike && (
                <OfficeDocPreview attId={att.id} fileName={att.file_name} url={url} />
            )}
        </section>
    );
}

function OfficeDocPreview({ attId, fileName, url }: { attId: string; fileName: string; url: string }) {
    const [data, setData] = useState<{ rows: string[][]; error: string | null } | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API_URL}/emails/attachments/${attId}/preview`);
                if (!res.ok) throw new Error(`API ${res.status}`);
                const j = await res.json();
                if (!cancelled) setData({ rows: j.rows ?? [], error: j.error ?? null });
            } catch (e) {
                if (!cancelled) setData({ rows: [], error: e instanceof Error ? e.message : 'Lỗi' });
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [attId]);

    if (loading) return <div className="p-6 text-sm text-slate-400">Đang đọc {fileName}...</div>;
    if ((data?.error || (data?.rows.length ?? 0) === 0) && fileName.toLowerCase().endsWith('.xlsx')) {
        return (
            <div className="p-4 bg-amber-50">
                <p className="text-xs text-amber-700 mb-2">Không trích tự động được — <a href={url} download={fileName} className="underline">Tải gốc</a> để tải file gốc.</p>
                {data?.error && <p className="text-xs text-slate-500 mt-1">{data.error}</p>}
            </div>
        );
    }
    if ((data?.rows.length ?? 0) === 0) return <div className="p-4 text-sm text-slate-400">Không trích được nội dung — <a href={url} download={fileName} className="text-blue-600 hover:underline">Tải gốc</a></div>;

    return (
        <div className="overflow-x-auto max-h-[520px] overflow-y-auto bg-white">
            <table className="w-full text-left text-sm border-collapse">
                <tbody>
                    {(data?.rows ?? []).map((row, i) => (
                        <tr key={i} className={i === 0 ? 'bg-slate-800 text-white font-semibold' : 'border-b border-slate-100'}>
                            {row.map((cell, j) => (
                                <td key={j} className="px-4 py-2 border-r border-slate-100 last:border-0 whitespace-pre-wrap">{cell || ''}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// Lịch sử hội thoại: hiển thị toàn bộ các email cùng thread_id
function ThreadHistory({ emailId, currentId }: { emailId: string; currentId: string }) {
    const [items, setItems] = useState<ThreadItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API_URL}/emails/${emailId}/thread`);
                if (!res.ok) throw new Error(`API ${res.status}`);
                const data = await res.json();
                if (!cancelled) setItems(data.items ?? []);
            } catch {
                // bỏ qua — section chỉ hiển thị nếu tải được
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [emailId]);

    if (loading) return null;
    if (items.length <= 1) return null;

    return (
        <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-1 border-b border-slate-100 pb-2">
                Lịch sử hội thoại ({items.length} email)
            </h2>
            <p className="text-xs text-slate-400 mt-2">Các email cùng một luồng trao đổi — nhấn để xem nội dung.</p>

            <ol className="mt-4 space-y-3">
                {items.map((it, idx) => {
                    const isCurrent = it.id_email === currentId;
                    const expanded = expandedId === it.id_email;
                    return (
                        <li key={it.id_email} className={`rounded-lg border ${isCurrent ? 'border-blue-300 bg-blue-50/50' : 'border-slate-200'}`}>
                            <button
                                onClick={() => setExpandedId(expanded ? null : it.id_email)}
                                className="w-full text-left px-4 py-3 flex items-start justify-between gap-3"
                            >
                                <div className="min-w-0">
                                    <p className="text-sm font-semibold text-slate-800 truncate">
                                        <span className="text-slate-400 font-mono mr-2">#{idx + 1}</span>
                                        {it.sender_name ?? it.sender_email}
                                        {isCurrent && <span className="ml-2 text-[11px] text-blue-600 font-bold">(email này)</span>}
                                    </p>
                                    <p className="text-xs text-slate-500 mt-0.5 truncate">{it.subject}</p>
                                </div>
                                <span className="text-xs text-slate-400 shrink-0">{formatDate(it.sent_at)}</span>
                            </button>
                            {expanded && (
                                <div className="px-4 pb-4 border-t border-slate-100 pt-3">
                                    <p className="text-xs text-slate-400 mb-2">Tóm tắt: {it.content_summarized || '—'}</p>
                                    <div className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded-md p-3 max-h-72 overflow-y-auto">
                                        {it.body_clean ?? '—'}
                                    </div>
                                    {it.has_attachments && (
                                        <Link href={`/emails/${it.id_email}`} className="text-blue-600 text-xs hover:underline inline-flex items-center gap-1 mt-2">
                                            <Paperclip className="h-3 w-3" /> Xem email này kèm file
                                        </Link>
                                    )}
                                </div>
                            )}
                        </li>
                    );
                })}
            </ol>
        </section>
    );
}

// ---------- Page ----------
export default function EmailDetailFullPage({ params }: { params: Promise<{ id: string }> }) {
    const { id: emailId } = use(params);
    const [email, setEmail] = useState<EmailDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
    const [isApproved, setIsApproved] = useState(false);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API_URL}/emails/${emailId}`);
                if (!res.ok) throw new Error(`API ${res.status}`);
                const data: EmailDetail = await res.json();
                if (!cancelled) {
                    setEmail(data);
                    const primary = data.assigned_labels.find((l) => l.source === 'user');
                    if (primary) {
                        setSelectedLabel(primary.label_name);
                        setIsApproved(true);
                    }
                }
            } catch (e) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Lỗi tải email');
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [emailId]);

    const handleApprove = async () => {
        if (!selectedLabel || !email) return;
        setSaving(true);
        try {
            const res = await fetch(`${API_URL}/emails/${email.id_email}/labels`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label_id: selectedLabel, reason: 'Người dùng gán thủ công từ UI' }),
            });
            if (!res.ok) throw new Error(`API ${res.status}`);
            setIsApproved(true);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Lỗi gán nhãn');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-100 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            </div>
        );
    }

    if (error || !email) {
        return (
            <div className="min-h-screen bg-slate-100 flex flex-col items-center justify-center gap-4">
                <p className="text-slate-600">Không tải được email: {error ?? 'không rõ'}</p>
                <Link href="/" className="text-blue-600 hover:underline flex items-center gap-2">
                    <ArrowLeft className="h-4 w-4" /> Về hộp thư
                </Link>
            </div>
        );
    }

    const sec = email.ai_analysis.security;
    const risk = sec?.risk_level ?? 'low';
    const actionItems = email.ai_analysis.key_points?.action_items ?? [];

    return (
        <div className="min-h-screen bg-slate-100 font-sans pb-12">
            {/* 1. TOP NAVIGATION */}
            <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-50 shadow-sm flex items-center justify-between">
                <div className="flex items-center gap-4 min-w-0">
                    <Link href="/" className="p-2 text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-full transition shrink-0">
                        <ArrowLeft className="h-5 w-5" />
                    </Link>
                    <div className="min-w-0">
                        <h1 className="text-xl font-bold text-slate-800 truncate">{email.metadata.subject}</h1>
                        <p className="text-sm text-slate-500">{formatDate(email.metadata.received_at)}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    {risk !== 'low' && (
                        <div className="px-3 py-1 bg-red-100 text-red-700 font-medium text-sm rounded-full flex items-center gap-2">
                            <AlertCircle className="h-4 w-4" /> Rủi ro: {risk}
                        </div>
                    )}
                    <div className={`px-3 py-1 font-medium text-sm rounded-full flex items-center gap-2 ${isApproved ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                        <AlertCircle className="h-4 w-4" /> {isApproved ? 'Đã duyệt nhãn' : 'Đang chờ duyệt nhãn'}
                    </div>
                </div>
            </header>

            {/* 2. MAIN GRID LAYOUT */}
            <div className="max-w-[1400px] mx-auto mt-6 px-6 grid grid-cols-1 xl:grid-cols-12 gap-6">

                {/* CỘT TRÁI (70%): THÔNG TIN CHI TIẾT */}
                <div className="xl:col-span-8 space-y-6">

                    {/* Phần 1: Định danh email */}
                    <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-2 border-b border-slate-100 pb-2">1. Định danh email</h2>
                        <Field label="id_email"><Mono>{email.id_email}</Mono></Field>
                        <Field label="Tiêu đề">{email.metadata.subject}</Field>
                        <Field label="id_mailbox"><Mono>{email.id_mailbox}</Mono></Field>
                    </section>

                    {/* Phần 2: Thông tin người gửi */}
                    <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-2 border-b border-slate-100 pb-2">2. Thông tin người gửi</h2>
                        <Field label="Tên"><span className="flex items-center gap-2"><User className="h-4 w-4 text-slate-400" />{email.contact.name ?? '—'}</span></Field>
                        <Field label="id_sender"><Mono>{email.contact.id_sender ?? '—'}</Mono></Field>
                        <Field label="Email"><span className="flex items-center gap-2"><Mail className="h-4 w-4 text-slate-400" />{email.contact.email ?? '—'}</span></Field>
                        <Field label="CC">
                            {email.contact.cc_emails.length > 0 ? (
                                <ul className="space-y-1">{email.contact.cc_emails.map((c) => <li key={c} className="break-all">{c}</li>)}</ul>
                            ) : <span className="text-slate-400">—</span>}
                        </Field>
                        <Field label="BCC">
                            {email.contact.bcc_emails.length > 0 ? (
                                <ul className="space-y-1">{email.contact.bcc_emails.map((c) => <li key={c} className="break-all">{c}</li>)}</ul>
                            ) : <span className="text-slate-400">—</span>}
                        </Field>
                        <Field label="Điện thoại"><span className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" />{email.contact.phone ?? '—'}</span></Field>
                        <Field label="Công ty"><span className="flex items-center gap-2"><Building2 className="h-4 w-4 text-slate-400" />{email.contact.company ?? '—'}</span></Field>
                        <Field label="Nội bộ"><Badge ok={email.contact.is_internal} text={email.contact.is_internal ? 'Nội bộ' : 'Bên ngoài'} /></Field>
                        <Field label="Khách quen"><Badge ok={email.contact.is_known_customer} text={email.contact.is_known_customer ? 'Khách hàng quen' : 'Mới / chưa xác định'} /></Field>
                    </section>

                    {/* Phần 3: Nội dung email */}
                    <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-2 border-b border-slate-100 pb-2">3. Thông tin nội dung email</h2>
                        <Field label="message_id"><Mono>{email.content.message_id}</Mono></Field>
                        <Field label="thread_id"><Mono>{email.content.thread_id ?? '—'}</Mono></Field>
                        <Field label="in_reply_to"><Mono>{email.content.in_reply_to ?? '—'}</Mono></Field>
                        <div className="py-2">
                            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">body_clean</span>
                            <div className="mt-1 prose prose-sm max-w-none text-slate-700 leading-relaxed bg-slate-50 p-6 rounded-lg border border-slate-100 whitespace-pre-wrap">
                                {email.content.body_clean ?? <span className="text-slate-400">—</span>}
                            </div>
                        </div>
                        <Field label="Tóm tắt AI">{email.content.content_summarized || <span className="text-slate-400">—</span>}</Field>
                        <Field label="received_at">{formatDate(email.content.received_at)}</Field>
                        <Field label="Đính kèm"><Badge ok={email.content.has_attachments} text={email.content.has_attachments ? `Có (${email.attachments.length} file)` : 'Không'} /></Field>
                    </section>

                    {/* Phần 4: Thông tin file đính kèm */}
                    <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-2 border-b border-slate-100 pb-2">4. Thông tin file đính kèm</h2>
                        {email.attachments.length === 0 ? (
                            <p className="text-sm text-slate-400 py-2">Email này không có file đính kèm.</p>
                        ) : (
                            email.attachments.map((att) => (
                                <div key={att.id} className="py-3 border-b border-slate-100 last:border-0">
                                    <Field label="id_attachment"><Mono>{att.id}</Mono></Field>
                                    <Field label="file_name"><span className="flex items-center gap-2"><Paperclip className="h-4 w-4 text-slate-400" />{att.file_name}</span></Field>
                                    <Field label="mime_type">{att.mime_type ?? '—'}</Field>
                                    <Field label="size_bytes">{formatBytes(att.size_bytes)} ({att.size_bytes} bytes)</Field>
                                    <Field label="storage_key"><Mono>{att.storage_key}</Mono></Field>
                                    <Field label="is_inline"><Badge ok={!att.is_inline} text={att.is_inline ? 'Ảnh inline' : 'File độc lập'} /></Field>
                                    <Field label="process_status">{att.process_status}</Field>
                                </div>
                            ))
                        )}
                    </section>

                    {/* Preview file trực tiếp */}
                    {email.attachments.map((att) => (
                        <AttachmentViewer key={att.id} att={att} />
                    ))}

                    {/* Lịch sử hội thoại (thread) */}
                    <ThreadHistory emailId={email.id_email} currentId={email.id_email} />
                </div>

                {/* CỘT PHẢI (30%): HÀNH ĐỘNG & AI SUMMARY */}
                <div className="xl:col-span-4 space-y-6">
                    <div className="sticky top-24 space-y-6">

                        {/* 1. KHU VỰC GÁN NHÃN */}
                        <div className="bg-white rounded-xl border-2 border-blue-100 shadow-md p-5 relative overflow-hidden">
                            <div className="absolute top-0 left-0 w-full h-1 bg-blue-600"></div>
                            <h2 className="text-base font-bold text-slate-800 mb-1">Xác nhận Nghiệp vụ</h2>
                            <p className="text-xs text-slate-500 mb-4">Chọn nhãn để hệ thống kích hoạt luồng xử lý tương ứng.</p>

                            <div className="border border-slate-200 rounded-lg overflow-hidden mb-4">
                                <div className="max-h-48 overflow-y-auto bg-slate-50 p-1.5 space-y-1 custom-scrollbar">
                                    {LABELS.map((label) => (
                                        <button
                                            key={label.id}
                                            onClick={() => { setSelectedLabel(label.id); setIsApproved(false); }}
                                            className={`w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-all flex items-center justify-between ${selectedLabel === label.id
                                                ? 'bg-blue-600 text-white shadow-sm'
                                                : 'text-slate-600 hover:bg-slate-200'
                                                }`}
                                        >
                                            {label.name}
                                            {selectedLabel === label.id && <Check className="h-4 w-4 text-white" />}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <button
                                onClick={handleApprove}
                                disabled={!selectedLabel || isApproved || saving}
                                className={`w-full py-2.5 rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-all ${isApproved
                                    ? 'bg-emerald-500 text-white'
                                    : selectedLabel
                                        ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md hover:shadow-lg transform hover:-translate-y-0.5'
                                        : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                    }`}
                            >
                                {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Đang lưu...</> : isApproved ? 'Đã duyệt thành công' : 'Duyệt & Chạy AI Agent'}
                            </button>
                        </div>

                        {/* 2. AI SUMMARY TỔNG QUAN */}
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                            <h3 className="font-bold text-slate-800 mb-5 flex items-center gap-2 border-b border-slate-100 pb-3">✨ Phân tích từ AI</h3>

                            <div className="space-y-5 text-sm">
                                {sec && ((sec.flags ?? []).length > 0 || sec.is_phishing || sec.is_spam) && (
                                    <div className="p-3 bg-red-50 border border-red-100 rounded-lg">
                                        <p className="text-red-700 text-xs font-bold uppercase tracking-wider mb-1">Cảnh báo bảo mật ({risk})</p>
                                        <ul className="text-red-700 text-sm space-y-1">
                                            {(sec.flags ?? []).map((f) => <li key={f}>• {f}</li>)}
                                            {sec.is_phishing && <li>• Nghi ngờ lừa đảo</li>}
                                            {sec.is_spam && <li>• Nghi ngờ thư rác</li>}
                                        </ul>
                                    </div>
                                )}

                                <div>
                                    <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">Tóm tắt nội dung (TL;DR)</p>
                                    <p className="text-slate-700 leading-relaxed">{email.ai_analysis.tldr || '—'}</p>
                                </div>

                                {actionItems.length > 0 && (
                                    <div>
                                        <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-3">Công việc cần xử lý</p>
                                        <ul className="space-y-3">
                                            {actionItems.map((item, i) => (
                                                <li key={i} className="flex items-start gap-2.5 bg-slate-50 p-3 rounded-lg border border-slate-200">
                                                    <CheckSquare className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />
                                                    <span className="text-slate-700">
                                                        {item.task}
                                                        {item.due_date && <span className="block text-xs text-slate-400 mt-1">Hạn: {item.due_date}</span>}
                                                    </span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {email.ai_analysis.key_points?.sentiment && (
                                    <div>
                                        <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">Sắc thái</p>
                                        <Badge ok={email.ai_analysis.key_points.sentiment !== 'negative'} text={email.ai_analysis.key_points.sentiment} />
                                    </div>
                                )}
                            </div>
                        </div>

                    </div>
                </div>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      ` }} />
        </div>
    );
}
