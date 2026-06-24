import { Route, Routes } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { LeadDetailPage } from "./pages/LeadDetailPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/leads/:id" element={<LeadDetailPage />} />
    </Routes>
  );
}
