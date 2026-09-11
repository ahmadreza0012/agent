import { initializeApp, getApps } from 'firebase/app';
import { getFirestore, collection, doc, setDoc, getDocs, query, orderBy, limit, deleteDoc } from 'firebase/firestore';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let db = null;
let isInitialized = false;

export function getFirestoreDB() {
  if (db) return db;
  try {
    const configPath = path.join(__dirname, 'firebase-applet-config.json');
    if (!fs.existsSync(configPath)) {
      console.warn('[Firebase] Config file not found.');
      return null;
    }
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    const app = getApps().length === 0 ? initializeApp(config) : getApps()[0];
    db = getFirestore(app, config.firestoreDatabaseId || undefined);
    isInitialized = true;
    console.log('[Firebase] Connected to Cloud Firestore successfully.');
    return db;
  } catch (err) {
    console.warn('[Firebase Init Note]', err.message);
    return null;
  }
}

export async function syncTradeToFirestore(trade) {
  try {
    const firestore = getFirestoreDB();
    if (!firestore || !trade || !trade.id) return;
    const docRef = doc(firestore, 'closed_trades', String(trade.id));
    await setDoc(docRef, {
      ...trade,
      synced_at: new Date().toISOString()
    }, { merge: true });
  } catch (e) {
    console.warn('[Firebase Sync Trade Error]', e.message);
  }
}

export async function getClosedTradesFromFirestore(limitCount = 50) {
  try {
    const firestore = getFirestoreDB();
    if (!firestore) return null;
    const q = query(collection(firestore, 'closed_trades'), orderBy('closed_at', 'desc'), limit(limitCount));
    const snapshot = await getDocs(q);
    const trades = [];
    snapshot.forEach(docSnap => {
      trades.push(docSnap.data());
    });
    return trades.length > 0 ? trades : null;
  } catch (e) {
    console.warn('[Firebase Fetch Trades Note]', e.message);
    return null;
  }
}

export async function syncPositionToFirestore(pos) {
  try {
    const firestore = getFirestoreDB();
    if (!firestore || !pos || !pos.id) return;
    const docRef = doc(firestore, 'open_positions', String(pos.id));
    await setDoc(docRef, {
      ...pos,
      synced_at: new Date().toISOString()
    }, { merge: true });
  } catch (e) {
    console.warn('[Firebase Sync Position Error]', e.message);
  }
}

export async function removePositionFromFirestore(posId) {
  try {
    const firestore = getFirestoreDB();
    if (!firestore || !posId) return;
    await deleteDoc(doc(firestore, 'open_positions', String(posId)));
  } catch (e) {
    console.warn('[Firebase Remove Position Error]', e.message);
  }
}
