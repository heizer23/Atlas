/**
 * PersonalDevelopment ShellEntry
 *
 * React Router entry point for the Learning tile.
 * Owned by React.lazy in shellConfig.ts.
 *
 * Routes:
 *   /learning       → LearningPage (training unit list)
 *   /learning/new   → CreateTrainingUnitPage
 *   /learning/:unitId → UnitDetailPage
 */

import React, { Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Skeleton from '@platform-ui/components/Skeleton';

const LearningPage           = React.lazy(() => import('./LearningPage'));
const CreateTrainingUnitPage = React.lazy(() => import('./CreateTrainingUnitPage'));
const UnitDetailPage         = React.lazy(() => import('./UnitDetailPage'));

export default function ShellEntry() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <Suspense fallback={<Skeleton />}>
            <LearningPage />
          </Suspense>
        }
      />
      <Route
        path="/new"
        element={
          <Suspense fallback={<Skeleton />}>
            <CreateTrainingUnitPage />
          </Suspense>
        }
      />
      <Route
        path="/:unitId"
        element={
          <Suspense fallback={<Skeleton />}>
            <UnitDetailPage />
          </Suspense>
        }
      />
    </Routes>
  );
}
