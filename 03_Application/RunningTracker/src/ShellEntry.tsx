/**
 * RunningTracker ShellEntry - Sprint01_RecordAndSync
 *
 *   /running                -> RunPage      (Free Run explanation, prepared runs)
 *   /running/history        -> HistoryPage  (runs with sync state)
 *   /running/history/:id    -> RunDetailPage (charts, splits, comment; no map)
 *   /running/routes         -> RoutesPage   (route library)
 *   /running/devices        -> DevicesPage  (pair phone, device list)
 */

import React from 'react';
import { Route, Routes } from 'react-router-dom';
import RunPage from './RunPage';
import HistoryPage from './HistoryPage';
import RunDetailPage from './RunDetailPage';
import DevicesPage from './DevicesPage';
import RoutesPage from './RoutesPage';
import './running.css';

export default function ShellEntry() {
  return (
    <Routes>
      <Route path="/" element={<RunPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/history/:id" element={<RunDetailPage />} />
      <Route path="/routes" element={<RoutesPage />} />
      <Route path="/devices" element={<DevicesPage />} />
    </Routes>
  );
}
