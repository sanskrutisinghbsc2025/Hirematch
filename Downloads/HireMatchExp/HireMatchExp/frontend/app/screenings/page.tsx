"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Layers,
  PlusCircle,
  Search,
  ArrowRight,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { ScreeningSession } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";

export default function ScreeningsListPage() {
  const [sessions, setSessions] = useState<ScreeningSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchSessions = async () => {
    try {
      setLoading(true);
      const res = await apiClient.getSessions(1, 50);
      setSessions(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      setIsDeleting(true);
      await apiClient.deleteSession(deleteId);
      setSessions(sessions.filter((s) => s.id !== deleteId));
      setDeleteId(null);
    } catch (err) {
      alert("Failed to delete session");
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredSessions = sessions.filter((s) => {
    const title = s.title || s.name || "";
    return title.toLowerCase().includes(search.toLowerCase());
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-charcoal-900">
            Screening Sessions
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">
            Manage your open positions and review candidate pools.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchSessions}
            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          >
            Refresh
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              try {
                const res = await apiClient.cleanupDraftSessions();
                if (res.deleted_count > 0) {
                  alert(`Purged ${res.deleted_count} empty draft session(s).`);
                  fetchSessions();
                } else {
                  alert("No empty draft sessions found.");
                }
              } catch (err: any) {
                alert("Failed to cleanup drafts: " + err.message);
              }
            }}
            className="text-stone-400 hover:text-stone-600"
          >
            Purge Empty Drafts
          </Button>
          <Link href="/screenings/new">
            <Button
              variant="primary"
              size="sm"
              leftIcon={<PlusCircle className="h-4 w-4" />}
            >
              New Screening
            </Button>
          </Link>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-stone-400" />
          <input
            type="text"
            placeholder="Search sessions by title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-stone-300 bg-white py-2 pl-9 pr-4 text-xs sm:text-sm text-stone-900 placeholder-stone-400 focus:border-olive-500 focus:outline-none focus:ring-2 focus:ring-olive-500/20 transition-all"
          />
        </div>
        <p className="text-xs text-stone-500 shrink-0">
          Showing{" "}
          <span className="font-semibold text-stone-900 tabular-nums">{filteredSessions.length}</span>{" "}
          of{" "}
          <span className="font-semibold text-stone-900 tabular-nums">{total}</span> sessions
        </p>
      </div>

      {/* Sessions Grid */}
      {loading ? (
        <div className="py-20 text-center text-stone-400">
          <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-3 text-olive-600" />
          <p className="text-xs">Loading screening sessions...</p>
        </div>
      ) : filteredSessions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stone-300 bg-[#FAF9F6] p-14 text-center">
          <Layers className="h-9 w-9 text-stone-300 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-stone-900">
            {search ? "No sessions match your search" : "No screening sessions yet"}
          </h3>
          <p className="text-xs text-stone-500 mt-1 max-w-xs mx-auto">
            {search
              ? "Try adjusting your search terms or clear it to view all sessions."
              : "Create your first session to start screening candidates for an open position."}
          </p>
          {!search && (
            <div className="mt-5">
              <Link href="/screenings/new">
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<PlusCircle className="h-4 w-4" />}
                >
                  New Screening
                </Button>
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                "group relative flex flex-col justify-between rounded-xl border border-stone-300 bg-white p-5 shadow-subtle transition-all duration-200",
                "hover:border-stone-400 hover:shadow-card"
              )}
            >
              <div>
                {/* Top row: badge + delete */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <Badge status={session.status}>{session.status}</Badge>
                  <button
                    onClick={() => setDeleteId(session.id)}
                    className="text-stone-300 hover:text-terracotta-600 transition-colors p-1 rounded hover:bg-terracotta-50"
                    title="Delete session"
                    aria-label="Delete session"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                <Link href={`/screenings/${session.id}`}>
                  <h3 className="text-sm font-semibold text-stone-900 group-hover:text-olive-700 transition-colors line-clamp-1">
                    {(session as any).session_name ||
                      (session as any).job_title ||
                      session.title ||
                      session.name ||
                      "Screening Session"}
                  </h3>
                </Link>

                <p className="text-xs text-stone-500 mt-1.5 line-clamp-2 min-h-[34px] leading-relaxed">
                  {session.description || "No description provided."}
                </p>
              </div>

              {/* Footer */}
              <div className="mt-4 pt-3 border-t border-stone-200 flex items-center justify-between">
                <span className="text-xs text-stone-500">
                  <span className="font-semibold text-stone-900 tabular-nums">
                    {session.candidate_count ?? session.resume_count ?? 0}
                  </span>{" "}
                  resumes evaluated
                </span>

                <Link href={`/screenings/${session.id}`}>
                  <Button
                    variant="secondary"
                    size="sm"
                    rightIcon={<ArrowRight className="h-3 w-3" />}
                  >
                    Open
                  </Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Delete Screening Session"
        description="This action cannot be undone. The session and all associated candidate evaluations will be permanently removed."
        size="sm"
      >
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" size="sm" onClick={() => setDeleteId(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            isLoading={isDeleting}
            onClick={handleDelete}
          >
            Delete Session
          </Button>
        </div>
      </Modal>
    </div>
  );
}
