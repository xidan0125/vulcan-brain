import DashboardLayout from "@/components/layout/DashboardLayout";

export default function DataExplorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
