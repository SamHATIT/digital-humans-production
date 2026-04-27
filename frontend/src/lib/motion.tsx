import { forwardRef } from 'react';
import type { HTMLAttributes, ReactNode, Ref } from 'react';

/**
 * Shim minimal pour `framer-motion` — pas installé dans le projet.
 * Les pages legacy `pages/pm/*` (en attente de refonte A5.2/A5.3)
 * utilisaient `motion.div` pour des animations cosmétiques. Ce shim
 * absorbe les props d'animation (`initial`, `animate`, `transition`,
 * `whileHover`, `exit`, etc.) sans dépendance externe ni effet visuel.
 *
 * À retirer quand A5.3 refondra les pages PM avec une animation library
 * de premier ordre.
 */

type AnimateValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Record<string, unknown>
  | AnimateValue[];

interface MotionProps {
  children?: ReactNode;
  initial?: AnimateValue;
  animate?: AnimateValue;
  exit?: AnimateValue;
  transition?: AnimateValue;
  whileHover?: AnimateValue;
  whileTap?: AnimateValue;
  layoutId?: string;
}

type MotionDivProps = MotionProps & HTMLAttributes<HTMLDivElement>;

const MotionDiv = forwardRef<HTMLDivElement, MotionDivProps>(function MotionDiv(
  props,
  ref: Ref<HTMLDivElement>,
) {
  const {
    initial: _initial,
    animate: _animate,
    exit: _exit,
    transition: _transition,
    whileHover: _whileHover,
    whileTap: _whileTap,
    layoutId: _layoutId,
    children,
    ...rest
  } = props;
  return (
    <div ref={ref} {...rest}>
      {children}
    </div>
  );
});

export const motion = {
  div: MotionDiv,
};
