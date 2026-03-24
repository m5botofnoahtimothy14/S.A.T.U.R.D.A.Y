import { useState, useEffect, createContext, useContext } from 'react';
import { signInWithPopup, signOut, onAuthStateChanged, GoogleAuthProvider } from 'firebase/auth';
import { auth as firebaseAuth } from '../firebase';

const ADMIN_EMAILS = ['m5botkitm40@gmail.com', 'noahtimothykeba@gmail.com'];

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('aegis_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('aegis_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
      if (firebaseUser) {
        const idToken = await firebaseUser.getIdToken(true);
        const userData = {
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          role: 'admin', // Or dynamically fetched
          loginTime: new Date().toISOString()
        };
        setUser(userData);
        setToken(idToken);
        localStorage.setItem('aegis_user', JSON.stringify(userData));
        localStorage.setItem('aegis_token', idToken);
      } else {
        setUser(null);
        setToken(null);
        localStorage.removeItem('aegis_user');
        localStorage.removeItem('aegis_token');
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const login = async () => {
    try {
      const provider = new GoogleAuthProvider();
      const userCredential = await signInWithPopup(firebaseAuth, provider);
      const email = userCredential.user.email;
      const role = ADMIN_EMAILS.includes(email) ? 'admin' : 'viewer';

      const idToken = await userCredential.user.getIdToken(true);
      const userData = {
        uid: userCredential.user.uid,
        email: email,
        role: role,
        loginTime: new Date().toISOString()
      };

      setUser(userData);
      setToken(idToken);
      localStorage.setItem('aegis_user', JSON.stringify(userData));
      localStorage.setItem('aegis_token', idToken);

      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  };

  const logout = async () => {
    try {
      await signOut(firebaseAuth);
    } catch (error) {
      console.error('Logout error', error);
    }
  };

  const isAuthenticated = () => {
    return !!user && !!token;
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};
