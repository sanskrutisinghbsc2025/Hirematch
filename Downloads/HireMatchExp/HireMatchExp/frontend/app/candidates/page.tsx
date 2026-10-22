"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { RotateCcw } from "lucide-react";

export default function CandidatesIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/screenings");
  }, [router]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center text-stone-400">
      <RotateCcw className="h-5 w-5 animate-spin text-terra-500 mb-2" />
      <p className="text-sm">Redirecting to screening sessions...</p>
    </div>
  );
}
