import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { WorkoutDetail } from './components/WorkoutDetail';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#6750A4',
    },
    secondary: {
      main: '#625B71',
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
});

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="size-full flex items-center justify-center" style={{ backgroundColor: '#F3F0F7' }}>
        <WorkoutDetail />
      </div>
    </ThemeProvider>
  );
}