import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { Me, Member } from "@/lib/types";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => apiGet<Me>("/auth/me"), retry: false, staleTime: 60_000 });
}

export function useCan() {
  const { data } = useMe();
  return (perm: string) => !!data?.permissions.includes(perm);
}

export function useMembers(enabled = true) {
  return useQuery({
    queryKey: ["members"],
    queryFn: () => apiGet<Member[]>("/users"),
    enabled,
    staleTime: 60_000,
  });
}
