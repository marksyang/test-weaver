import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import PlaceholderPage from './PlaceholderPage';

describe('PlaceholderPage', () => {
  it('renders the title, description, "待開發" tag and planned alert', () => {
    render(<PlaceholderPage title="平台同步" desc="尚未建置的模組說明" />);
    expect(screen.getByText('平台同步')).toBeInTheDocument();
    expect(screen.getByText('尚未建置的模組說明')).toBeInTheDocument();
    expect(screen.getByText(/待開發/)).toBeInTheDocument();
    expect(screen.getByText('此模組規劃中')).toBeInTheDocument();
  });
});
