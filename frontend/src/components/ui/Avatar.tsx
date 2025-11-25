import React from 'react';

interface AvatarProps {
  src: string;
  alt: string;
  size?: 'sm' | 'md' | 'lg';
  isActive?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: 'w-8 h-8',
  md: 'w-12 h-12',
  lg: 'w-16 h-16',
};

const Avatar: React.FC<AvatarProps> = ({ src, alt, size = 'md', isActive = false, className = '' }) => {
  return (
    <div className={`relative ${className}`}>
      <img
        src={src}
        alt={alt}
        className={`${sizeClasses[size]} rounded-full object-cover border-2 ${
          isActive ? 'border-cyan-500 shadow-lg shadow-cyan-500/50' : 'border-slate-600'
        } transition-all duration-300`}
        onError={(e) => {
          // Fallback to initials if image fails
          const target = e.target as HTMLImageElement;
          target.style.display = 'none';
          target.parentElement!.innerHTML = `
            <div class="${sizeClasses[size]} rounded-full bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center text-white font-bold">
              ${alt.charAt(0).toUpperCase()}
            </div>
          `;
        }}
      />
      {isActive && (
        <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-slate-900 rounded-full animate-pulse" />
      )}
    </div>
  );
};

export default Avatar;
