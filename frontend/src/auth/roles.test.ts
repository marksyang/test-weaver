import { describe, expect, it } from 'vitest';
import { allowedPathsForRole } from './roles';

describe('allowedPathsForRole', () => {
  it('admin sees every menu (incl. platform + settings)', () => {
    const p = allowedPathsForRole('admin');
    expect(p).toContain('/platform');
    expect(p).toContain('/settings');
    expect(p).toContain('/report');
  });

  it('qa_lead sees report but not platform/settings', () => {
    const p = allowedPathsForRole('qa_lead');
    expect(p).toContain('/report');
    expect(p).not.toContain('/platform');
    expect(p).not.toContain('/settings');
  });

  it('tester sees core only (no report/platform/settings)', () => {
    const p = allowedPathsForRole('tester');
    expect(p).toContain('/defect');
    expect(p).not.toContain('/report');
    expect(p).not.toContain('/platform');
    expect(p).not.toContain('/settings');
  });

  it('unknown role falls back to tester (least privilege)', () => {
    expect(allowedPathsForRole('nobody')).toEqual(allowedPathsForRole('tester'));
  });
});
