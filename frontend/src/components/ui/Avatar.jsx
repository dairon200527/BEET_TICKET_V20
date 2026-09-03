import { initials } from '../../utils/format';

export default function Avatar({ name, size = 'md', tone = 'blue' }) {
  return (
    <span className={`avatar avatar-${size} ${tone === 'green' ? 'avatar-green' : ''}`}>
      {initials(name)}
    </span>
  );
}

export function AvatarMore({ count, size = 'sm' }) {
  return <span className={`avatar avatar-${size} avatar-more`}>+{count}</span>;
}
