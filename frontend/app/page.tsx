// app/page.tsx
import Link from 'next/link';
import { Search, Filter, UploadCloud, Paperclip, CheckSquare, AlertCircle } from 'lucide-react';
import { LABELS } from '@/lib/data';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api';

interface EmailListItem {
    id_email: string;
    subject: string;
    sender_name: string;
    sender_email: string;
    status: string;
    received_at: string | null;
    tldr: string;
    security_flags: { risk_level?: string; flags?: string[] } | null;
}

async function fetchEmails(): Promise<EmailListItem[]> {
    try {
        const res = await fetch(`${API_URL}/emails/?limit=100`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`API ${res.status}`);
        const data = await res.json();
        return data.items ?? [];
    } catch {
        return [];
    }
}

function avatarInitials(name: string): string {
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatDate(iso: string | null): string {
    if (!iso) return '';
    try {
        return new Date(iso).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
    } catch {
        return '';
    }
}

export default async function SmartInbox() {
    const emails = await fetchEmails();

    return (
        <div className="min-h-screen bg-slate-50 p-6 md:p-10 font-sans">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-800 tracking-tight">Hộp thư thông minh</h1>
                    <p className="text-sm text-slate-500 mt-1">{emails.length} email đã xử lý</p>
                </div>

                <div className="flex flex-wrap gap-3 w-full md:w-auto">
                    <div className="relative flex-1 md:w-64">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Tìm tiêu đề, nội dung..."
                            className="w-full pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow"
                        />
                    </div>
                    <button className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">
                        <Filter className="h-4 w-4" /> Lọc nhãn
                    </button>
                </div>
            </div>

            {emails.length === 0 && (
                <div className="text-center py-20 text-slate-400">
                    <p>Chưa có email nào trong hệ thống.</p>
                    <p className="text-sm mt-1">Hãy chạy backend và test bulk 30 email trước.</p>
                </div>
            )}

            {/* Email Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {emails.map((email) => {
                    const risk = email.security_flags?.risk_level ?? 'low';
                    const name = email.sender_name || 'Unknown';
                    const isHighRisk = risk === 'high' || risk === 'medium';

                    return (
                        <Link href={`/emails/${email.id_email}`} key={email.id_email} className="group block">
                            <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all cursor-pointer h-full flex flex-col">

                                {/* Sender Info */}
                                <div className="flex items-start justify-between mb-4">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-sm shrink-0">
                                            {avatarInitials(name)}
                                        </div>
                                        <div className="min-w-0">
                                            <h3 className="font-semibold text-slate-900 text-sm truncate">{name}</h3>
                                            <p className="text-xs text-slate-500 truncate">{email.sender_email}</p>
                                        </div>
                                    </div>
                                    <span className="text-xs text-slate-400 font-medium shrink-0 ml-2">{formatDate(email.received_at)}</span>
                                </div>

                                {/* Email Content */}
                                <h2 className="font-bold text-slate-800 mb-2 group-hover:text-blue-600 transition-colors line-clamp-1">{email.subject}</h2>
                                <p className="text-sm text-slate-600 mb-4 line-clamp-2 flex-grow">{email.tldr || '—'}</p>

                                {/* Security Flag */}
                                {isHighRisk && (
                                    <div className="mb-4 p-2 bg-red-50 border border-red-100 rounded-md flex items-start gap-2">
                                        <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
                                        <p className="text-xs text-red-700 font-medium">
                                            {email.security_flags?.flags?.[0] ?? `Rủi ro: ${risk}`}
                                        </p>
                                    </div>
                                )}

                                {/* Footer: status */}
                                <div className="flex items-center justify-between pt-4 border-t border-slate-100 gap-2">
                                    <span className="px-2.5 py-1 bg-slate-100 text-slate-600 rounded-md text-[11px] font-semibold tracking-wide uppercase">
                                        {email.status}
                                    </span>
                                    <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                                        <CheckSquare className="h-3.5 w-3.5 text-emerald-600" /> Xem chi tiết
                                    </span>
                                </div>
                            </div>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
