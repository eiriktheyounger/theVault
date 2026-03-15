import { useEffect, useState } from 'react';
import { getBuildId } from '../lib';

export default function BottomBar() {
  const [build, setBuild] = useState('unknown');

  useEffect(() => {
    (async () => {
      try {
        setBuild(await getBuildId());
      } catch {
        // ignore errors; retain 'unknown'
      }
    })();
  }, []);

  return (
    <footer className="text-center text-xs text-gray-500 py-2">Build: {build}</footer>
  );
}

