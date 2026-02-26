import { useEffect, useState } from 'react';

export default function FlashValue({
  value,
  className = '',
  formatter,
}: {
  value: number | string;
  className?: string;
  formatter?: (value: number | string) => string;
}) {
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    setFlash(true);
    const timeout = setTimeout(() => setFlash(false), 200);
    return () => clearTimeout(timeout);
  }, [value]);

  const display = formatter ? formatter(value) : String(value);

  return <span className={`${flash ? 'flash' : ''} ${className}`}>{display}</span>;
}
