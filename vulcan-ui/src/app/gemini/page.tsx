import DashboardLayout from "@/components/layout/DashboardLayout";
import GeminiChatV3 from "@/components/gemini/GeminiChatV3";

export default function GeminiPage() {
  return (
    <DashboardLayout>
      <GeminiChatV3 />
    </DashboardLayout>
  );
}
