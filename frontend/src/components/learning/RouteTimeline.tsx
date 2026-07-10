// components/learning/RouteTimeline.tsx

import React, { useMemo, useCallback } from 'react';
import type { RouteStep, RouteProgress, StepFilterStatus } from '../../types/learning';
import { StepNode } from './StepNode';
import { StepDetailPanel } from './StepDetailPanel';
import { Progress, Segmented, Empty } from 'antd';

interface RouteTimelineProps {
  steps: RouteStep[];
  progress: RouteProgress;
  currentStepId: string | null;
  selectedStepId: string | null;
  filterStatus: StepFilterStatus;
  stepLectureNoteMap?: Map<string, string>;
  onStepSelect: (stepId: string) => void;
  onStepGenerateLecture: (stepId: string) => void;
  onStepStartQA: (stepId: string) => void;
  onStepViewNote: (noteId: string) => void;
  onFilterChange: (status: StepFilterStatus) => void;
}

export const RouteTimeline: React.FC<RouteTimelineProps> = ({
  steps,
  progress,
  currentStepId,
  selectedStepId,
  filterStatus,
  stepLectureNoteMap,
  onStepSelect,
  onStepGenerateLecture,
  onStepStartQA,
  onStepViewNote,
  onFilterChange,
}) => {
  const filteredSteps = useMemo(() => {
    if (filterStatus === 'all') return steps;
    return steps.filter((step) => step.status === filterStatus);
  }, [steps, filterStatus]);

  // 各状态步骤计数
  const countByStatus = useMemo(() => ({
    all: steps.length,
    pending: steps.filter((s) => s.status === 'pending').length,
    in_progress: steps.filter((s) => s.status === 'in_progress').length,
    completed: steps.filter((s) => s.status === 'completed').length,
  }), [steps]);

  const dependencyMap = useMemo(() => {
    const map = new Map<string, string[]>();
    steps.forEach((step) => {
      if (step.prerequisites?.length > 0) {
        map.set(step.id, step.prerequisites);
      }
    });
    return map;
  }, [steps]);

  const selectedStep = useMemo(
    () => steps.find((s) => s.id === selectedStepId) || null,
    [steps, selectedStepId]
  );

  const handleStepClick = useCallback(
    (stepId: string) => {
      onStepSelect(stepId);
    },
    [onStepSelect]
  );

  return (
    <div className="route-timeline">
      <div className="route-timeline__header">
        <Progress
          percent={Math.round(progress.percentComplete)}
          status={progress.percentComplete === 100 ? 'success' : 'active'}
          format={() => `${progress.completedSteps}/${progress.totalSteps} 步骤`}
        />
        <div className="route-timeline__stats">
          <span>预计剩余 {progress.estimatedMinutesRemaining} 分钟</span>
        </div>
      </div>

      <Segmented
        className="route-timeline__filter"
        value={filterStatus}
        onChange={(value) => onFilterChange(value as StepFilterStatus)}
        options={[
          { label: `全部 (${countByStatus.all})`, value: 'all' },
          { label: `待学习 (${countByStatus.pending})`, value: 'pending' },
          { label: `进行中 (${countByStatus.in_progress})`, value: 'in_progress' },
          { label: `已完成 (${countByStatus.completed})`, value: 'completed' },
        ]}
      />

      <div className="route-timeline__steps">
        {filteredSteps.length === 0 ? (
          <Empty description="暂无符合条件的步骤" />
        ) : (
          filteredSteps.map((step, index) => (
            <StepNode
              key={step.id}
              step={step}
              order={index + 1}
              isCurrent={step.id === currentStepId}
              isSelected={step.id === selectedStepId}
              hasDependency={dependencyMap.has(step.id)}
              lectureNoteId={stepLectureNoteMap?.get(step.id) ?? null}
              prerequisiteNames={
                dependencyMap.get(step.id)?.map(
                  (preId) => steps.find((s) => s.id === preId)?.title || ''
                ) || []
              }
              onClick={() => handleStepClick(step.id)}
              onGenerateLecture={() => onStepGenerateLecture(step.id)}
              onStartQA={() => onStepStartQA(step.id)}
              onViewNote={() => {
                const noteId = stepLectureNoteMap?.get(step.id);
                if (noteId) onStepViewNote(noteId);
              }}
            />
          ))
        )}
      </div>

      {selectedStep && (
        <StepDetailPanel
          step={selectedStep}
          onClose={() => onStepSelect('')}
          onGenerateLecture={() => onStepGenerateLecture(selectedStep.id)}
          onStartQA={() => onStepStartQA(selectedStep.id)}
          lectureNoteId={stepLectureNoteMap?.get(selectedStep.id) ?? null}
        />
      )}
    </div>
  );
};
