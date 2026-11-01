import { useAuth } from "./auth";
export const useCanWrite = () => { const { user } = useAuth(); return user?.role === "owner" || user?.role === "admin"; };
