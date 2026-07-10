// components/review/ReviewCard.tsx

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import type { FlashcardContent } from '../../types/review';
import { Rate, Space } from 'antd';

interface ReviewCardProps {
  content: FlashcardContent;
  onRate: (rating: number) => void;
  isCompleted: boolean;
}

export const ReviewCard: React.FC<ReviewCardProps> = ({
  content,
  onRate,
  isCompleted,
}) => {
  const [isFlipped, setIsFlipped] = useState(false);

  const handleFlip = () => {
    if (!isCompleted) {
      setIsFlipped((prev) => !prev);
    }
  };

  const handleRate = (rating: number) => {
    onRate(rating);
    setTimeout(() => setIsFlipped(false), 300);
  };

  return (
    <div className="review-card" onClick={handleFlip}>
      <motion.div
        className="review-card__inner"
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.5 }}
      >
        <div
          className="review-card__face review-card__face--front"
        >
          <div className="review-card__label">问题</div>
          <div className="review-card__content">
            <ReactMarkdown>{content.front}</ReactMarkdown>
          </div>
          {content.hint && (
            <div className="review-card__hint">
              提示：{content.hint}
            </div>
          )}
          <div className="review-card__flip-hint">点击翻转查看答案</div>
        </div>

        <div
          className="review-card__face review-card__face--back"
        >
          <div className="review-card__label">答案</div>
          <div className="review-card__content">
            <ReactMarkdown>{content.back}</ReactMarkdown>
          </div>
        </div>
      </motion.div>

      {isFlipped && !isCompleted && (
        <div className="review-card__rating" onClick={(e) => e.stopPropagation()}>
          <Space direction="vertical" align="center">
            <span>掌握程度评分：</span>
            <Rate
              count={5}
              onChange={handleRate}
              tooltips={['完全不记得', '有点印象', '比较熟悉', '基本掌握', '完全掌握']}
            />
          </Space>
        </div>
      )}
    </div>
  );
};
