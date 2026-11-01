import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { AppShell, RequireAuth } from "./components/ui";
import { AuthProvider } from "./lib/auth";
import { Login, Register } from "./pages/AuthPages";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Customers from "./pages/Customers";
import CustomerProfile from "./pages/CustomerProfile";
import Program from "./pages/Program";
import Rewards from "./pages/Rewards";
import Segments from "./pages/Segments";
import Recommendations from "./pages/Recommendations";
import CampaignBuilder from "./pages/CampaignBuilder";
import CampaignAnalytics from "./pages/CampaignAnalytics";
import Settings from "./pages/Settings";

const nav = [
  { to: "/app", label: "Dashboard" }, { to: "/app/customers", label: "Customers" }, { to: "/app/program", label: "Loyalty program" },
  { to: "/app/rewards", label: "Reward catalog" }, { to: "/app/segments", label: "Segmentation" }, { to: "/app/recommendations", label: "AI recommendations" },
  { to: "/app/campaigns", label: "Campaign builder" }, { to: "/app/campaign-analytics", label: "Campaign analytics" }, { to: "/app/settings", label: "Organization" },
];

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login brand="LoyaltyIQ" />} />
          <Route path="/register" element={<Register brand="LoyaltyIQ" extra={[{ name: "organization_name", label: "Business name" }]} />} />
          <Route element={<RequireAuth />}>
            <Route path="/app" element={<AppShell brand="LoyaltyIQ" nav={nav} />}>
              <Route index element={<Dashboard />} />
              <Route path="customers" element={<Customers />} />
              <Route path="customers/:id" element={<CustomerProfile />} />
              <Route path="program" element={<Program />} />
              <Route path="rewards" element={<Rewards />} />
              <Route path="segments" element={<Segments />} />
              <Route path="recommendations" element={<Recommendations />} />
              <Route path="campaigns" element={<CampaignBuilder />} />
              <Route path="campaign-analytics" element={<CampaignAnalytics />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
