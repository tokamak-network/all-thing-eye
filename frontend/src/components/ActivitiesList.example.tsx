/**
 * Example Usage of ActivitiesList Component
 * 
 * This file demonstrates how to use the ActivitiesList component in different scenarios.
 * Copy the relevant example to your page and customize as needed.
 */

"use client";

import { useState } from "react";
import ActivitiesList from "./ActivitiesList";
import { api as apiClient } from "@/lib/api";

/**
 * Example 1: Basic Usage (Simple Activities List)
 * Use this for member detail pages or project pages with minimal features
 */
export function BasicActivitiesListExample({ activities }: { activities: any[] }) {
  return (
    <ActivitiesList
      activities={activities}
      loading={false}
      error={null}
    />
  );
}

/**
 * Example 2: With Translation Feature
 * Use this for pages that need translation support (Slack messages, Notion pages, etc.)
 */
export function ActivitiesListWithTranslation({ activities }: { activities: any[] }) {
  const [translations, setTranslations] = useState<Record<string, { text: string; lang: string }>>({});
  const [translating, setTranslating] = useState<string | null>(null);
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);

  const handleTranslate = async (activityId: string, text: string, targetLang: string) => {
    setTranslating(activityId);
    try {
      const response = await apiClient.translateText(text, targetLang);
      setTranslations({
        ...translations,
        [activityId]: {
          text: response.translatedText,
          lang: targetLang,
        },
      });
    } catch (error) {
      console.error("Translation failed:", error);
      alert("Translation failed. Please try again.");
    } finally {
      setTranslating(null);
    }
  };

  return (
    <ActivitiesList
      activities={activities}
      loading={false}
      error={null}
      expandedActivity={expandedActivity}
      onToggleActivity={setExpandedActivity}
      enableTranslation={true}
      onTranslate={handleTranslate}
      translations={translations}
      translating={translating}
    />
  );
}

/**
 * Example 3: With Daily Analysis Feature
 * Use this for pages that display recordings_daily activities
 */
export function ActivitiesListWithDailyAnalysis({ activities }: { activities: any[] }) {
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);
  const [showDailyAnalysisModal, setShowDailyAnalysisModal] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState<any>(null);
  const [analysisTab, setAnalysisTab] = useState<string>("overview");

  const handleDailyAnalysisClick = async (activity: any, tab: string) => {
    setAnalysisTab(tab);
    setShowDailyAnalysisModal(true);
    
    try {
      const targetDate = activity.metadata?.target_date;
      if (targetDate) {
        const response = await apiClient.getRecordingsDailyByDate(targetDate);
        setSelectedAnalysis(response);
      }
    } catch (error) {
      console.error("Failed to load daily analysis:", error);
      alert("Failed to load daily analysis details");
    }
  };

  return (
    <>
      <ActivitiesList
        activities={activities}
        loading={false}
        error={null}
        expandedActivity={expandedActivity}
        onToggleActivity={setExpandedActivity}
        enableDailyAnalysis={true}
        onDailyAnalysisClick={handleDailyAnalysisClick}
      />

      {/* Add your modal component here to display daily analysis */}
      {showDailyAnalysisModal && selectedAnalysis && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-4">Daily Analysis</h2>
            {/* Display analysis content based on analysisTab */}
            <pre>{JSON.stringify(selectedAnalysis, null, 2)}</pre>
            <button
              onClick={() => setShowDailyAnalysisModal(false)}
              className="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/**
 * Example 4: Full-Featured (All Features Enabled)
 * Use this for the main /activities page with all features
 */
export function FullFeaturedActivitiesList({ 
  activities,
  notionUuidMap 
}: { 
  activities: any[];
  notionUuidMap: Record<string, string>;
}) {
  const [translations, setTranslations] = useState<Record<string, { text: string; lang: string }>>({});
  const [translating, setTranslating] = useState<string | null>(null);
  const [expandedActivity, setExpandedActivity] = useState<string | null>(null);
  const [showDailyAnalysisModal, setShowDailyAnalysisModal] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState<any>(null);

  const handleTranslate = async (activityId: string, text: string, targetLang: string) => {
    setTranslating(activityId);
    try {
      const response = await apiClient.translateText(text, targetLang);
      setTranslations({
        ...translations,
        [activityId]: {
          text: response.translatedText,
          lang: targetLang,
        },
      });
    } catch (error) {
      console.error("Translation failed:", error);
      alert("Translation failed. Please try again.");
    } finally {
      setTranslating(null);
    }
  };

  const handleDailyAnalysisClick = async (activity: any, tab: string) => {
    setShowDailyAnalysisModal(true);
    
    try {
      const targetDate = activity.metadata?.target_date;
      if (targetDate) {
        const response = await apiClient.getRecordingsDailyByDate(targetDate);
        setSelectedAnalysis(response);
      }
    } catch (error) {
      console.error("Failed to load daily analysis:", error);
      alert("Failed to load daily analysis details");
    }
  };

  return (
    <>
      <ActivitiesList
        activities={activities}
        loading={false}
        error={null}
        expandedActivity={expandedActivity}
        onToggleActivity={setExpandedActivity}
        enableTranslation={true}
        onTranslate={handleTranslate}
        translations={translations}
        translating={translating}
        enableDailyAnalysis={true}
        onDailyAnalysisClick={handleDailyAnalysisClick}
        notionUuidMap={notionUuidMap}
        apiClient={apiClient}
      />

      {/* Daily Analysis Modal */}
      {showDailyAnalysisModal && selectedAnalysis && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-4">Daily Analysis</h2>
            <pre>{JSON.stringify(selectedAnalysis, null, 2)}</pre>
            <button
              onClick={() => setShowDailyAnalysisModal(false)}
              className="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/**
 * Example 5: With Loading and Error States
 * Use this when fetching data from API
 */
export function ActivitiesListWithStates({ 
  activities,
  loading,
  error 
}: { 
  activities: any[];
  loading: boolean;
  error: Error | null;
}) {
  return (
    <ActivitiesList
      activities={activities}
      loading={loading}
      error={error}
      showEmpty={true}
    />
  );
}


