"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { isAdmin } from "@/lib/api";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/login");
      else if (isAdmin(user)) router.replace("/admin");
      else router.replace("/dashboard");
    }
  }, [user, loading, router]);

  return null;
}
