'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { User, login as apiLogin, getMe, getSoulStatus } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  // 新增：校准状态
  genesisCompleted: boolean;
  checkingCalibration: boolean;
  refreshCalibrationStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// 不需要校准检查的路由白名单
const CALIBRATION_WHITELIST = ['/login', '/calibration', '/register'];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [genesisCompleted, setGenesisCompleted] = useState(false);
  const [checkingCalibration, setCheckingCalibration] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // 检查校准状态
  const refreshCalibrationStatus = async () => {
    try {
      const status = await getSoulStatus();
      setGenesisCompleted(status.genesis_completed || false);
    } catch (error) {
      console.error('Failed to check calibration status:', error);
      // 降级：检查本地存储
      const localComplete = localStorage.getItem('vulcan_genesis_complete');
      setGenesisCompleted(localComplete === 'true');
    }
    setCheckingCalibration(false);
  };

  useEffect(() => {
    // Check for existing token on mount
    const checkAuth = async () => {
      const token = localStorage.getItem('vulcan_token');
      if (token) {
        try {
          const userData = await getMe();
          setUser(userData);
          // 同时检查校准状态
          await refreshCalibrationStatus();
        } catch (error) {
          // Token invalid, clear it
          localStorage.removeItem('vulcan_token');
          localStorage.removeItem('vulcan_user');
          setCheckingCalibration(false);
        }
      } else {
        setCheckingCalibration(false);
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  // 校准守卫：已登录但未完成校准的用户，强制重定向
  useEffect(() => {
    if (loading || checkingCalibration) return;

    const isWhitelisted = CALIBRATION_WHITELIST.some(path => pathname.startsWith(path));

    if (user && !genesisCompleted && !isWhitelisted) {
      console.log('[CalibrationGuard] User not calibrated, redirecting to /calibration');
      router.push('/calibration');
    }
  }, [loading, checkingCalibration, user, genesisCompleted, pathname, router]);

  const login = async (username: string, password: string) => {
    const response = await apiLogin(username, password);
    localStorage.setItem('vulcan_token', response.token);
    localStorage.setItem('vulcan_user', JSON.stringify(response.user));
    setUser(response.user);

    // 检查登录响应中的 genesis_completed
    const completed = response.user.genesis_completed || false;
    setGenesisCompleted(completed);
    setCheckingCalibration(false);

    // 登录后根据校准状态决定跳转
    if (completed) {
      router.push('/');
    } else {
      router.push('/calibration');
    }
  };

  const logout = () => {
    localStorage.removeItem('vulcan_token');
    localStorage.removeItem('vulcan_user');
    localStorage.removeItem('vulcan_genesis_complete');
    setUser(null);
    setGenesisCompleted(false);
    router.push('/login');
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      logout,
      isAuthenticated: !!user,
      genesisCompleted,
      checkingCalibration,
      refreshCalibrationStatus
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
