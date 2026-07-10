// components/review/QuizCard.tsx

import React, { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import type { QuizContent } from '../../types/review';
import { Button, Radio, Space, Tag } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';

interface QuizCardProps {
  content: QuizContent;
  onAnswer: (selectedIndex: number, isCorrect: boolean) => void;
  isCompleted: boolean;
}

export const QuizCard: React.FC<QuizCardProps> = ({
  content,
  onAnswer,
  isCompleted,
}) => {
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const isCorrect = selectedOption === content.correctIndex;

  const handleSubmit = useCallback(() => {
    if (selectedOption === null) return;
    setIsSubmitted(true);
    onAnswer(selectedOption, selectedOption === content.correctIndex);
  }, [selectedOption, content.correctIndex, onAnswer]);

  const optionLabels = ['A', 'B', 'C', 'D', 'E', 'F'];

  return (
    <div className="quiz-card">
      <div className="quiz-card__question">
        <ReactMarkdown>{content.question}</ReactMarkdown>
      </div>

      <Radio.Group
        className="quiz-card__options"
        value={selectedOption}
        onChange={(e) => !isSubmitted && setSelectedOption(e.target.value)}
        disabled={isSubmitted}
      >
        <Space direction="vertical" className="quiz-card__option-list">
          {content.options.map((option, index) => {
            let optionClassName = 'quiz-card__option';
            if (isSubmitted) {
              if (index === content.correctIndex) {
                optionClassName += ' quiz-card__option--correct';
              } else if (index === selectedOption && !isCorrect) {
                optionClassName += ' quiz-card__option--wrong';
              }
            }

            return (
              <div key={index} className={optionClassName}>
                <Radio value={index}>
                  <span className="quiz-card__option-label">
                    {optionLabels[index]}
                  </span>
                  <span className="quiz-card__option-content">
                    {option.content}
                  </span>
                </Radio>
                {isSubmitted && index === content.correctIndex && (
                  <CheckCircleOutlined className="quiz-card__option-icon quiz-card__option-icon--correct" />
                )}
                {isSubmitted && index === selectedOption && !isCorrect && (
                  <CloseCircleOutlined className="quiz-card__option-icon quiz-card__option-icon--wrong" />
                )}
              </div>
            );
          })}
        </Space>
      </Radio.Group>

      {!isSubmitted && (
        <Button
          type="primary"
          onClick={handleSubmit}
          disabled={selectedOption === null}
          block
        >
          确认答案
        </Button>
      )}

      {isSubmitted && (
        <div className="quiz-card__result">
          <Tag
            color={isCorrect ? 'success' : 'error'}
            className="quiz-card__result-tag"
          >
            {isCorrect ? '回答正确' : '回答错误'}
          </Tag>
          <div className="quiz-card__explanation">
            <h4>解析</h4>
            <ReactMarkdown>{content.explanation}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};
