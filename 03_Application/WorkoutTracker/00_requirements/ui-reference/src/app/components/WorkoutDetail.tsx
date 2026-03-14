import { useState } from 'react';
import {
  Card,
  CardContent,
  TextField,
  IconButton,
  Typography,
  Box,
  Chip,
  Divider,
} from '@mui/material';
import {
  FitnessCenter,
  Done,
  Close,
  Add,
  Remove,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface SetData {
  id: number;
  reps: string;
  completed: boolean;
}

// Mock historical data
const historicalData = [
  { date: 'Mar 7', set1: 10, set2: 10, set3: 8, set4: 8, set5: 6, weight: 55 },
  { date: 'Mar 9', set1: 10, set2: 10, set3: 9, set4: 8, set5: 7, weight: 57.5 },
  { date: 'Mar 11', set1: 10, set2: 10, set3: 10, set4: 8, set5: 8, weight: 57.5 },
  { date: 'Mar 13', set1: 10, set2: 10, set3: 10, set4: 9, set5: 8, weight: 60 },
];

export function WorkoutDetail() {
  const [exerciseName, setExerciseName] = useState('Bench Press');
  const [weight, setWeight] = useState('60');
  const [comment, setComment] = useState('');
  const [sets, setSets] = useState<SetData[]>([
    { id: 1, reps: '10', completed: false },
    { id: 2, reps: '10', completed: false },
    { id: 3, reps: '8', completed: false },
    { id: 4, reps: '8', completed: false },
    { id: 5, reps: '6', completed: false },
  ]);

  const toggleSetCompletion = (id: number) => {
    setSets(sets.map(set => 
      set.id === id ? { ...set, completed: !set.completed } : set
    ));
  };

  const updateReps = (id: number, reps: string) => {
    setSets(sets.map(set => 
      set.id === id ? { ...set, reps } : set
    ));
  };

  const incrementReps = (id: number) => {
    setSets(sets.map(set => {
      if (set.id === id) {
        const currentReps = parseInt(set.reps) || 0;
        return { ...set, reps: (currentReps + 1).toString() };
      }
      return set;
    }));
  };

  const decrementReps = (id: number) => {
    setSets(sets.map(set => {
      if (set.id === id) {
        const currentReps = parseInt(set.reps) || 0;
        return { ...set, reps: Math.max(0, currentReps - 1).toString() };
      }
      return set;
    }));
  };

  const completedSets = sets.filter(set => set.completed).length;

  // Prepare chart data
  const currentWorkout = {
    date: 'Today',
    set1: parseInt(sets[0].reps) || 0,
    set2: parseInt(sets[1].reps) || 0,
    set3: parseInt(sets[2].reps) || 0,
    set4: parseInt(sets[3].reps) || 0,
    set5: parseInt(sets[4].reps) || 0,
    weight: parseFloat(weight) || 0,
  };

  const chartData = [...historicalData, currentWorkout];

  const setColors = ['#6750A4', '#7965AF', '#8B7AB9', '#9D8FC4', '#AFA4CF'];

  return (
    <Box sx={{ maxWidth: 600, mx: 'auto', p: 2 }}>
      <Card elevation={2} sx={{ borderRadius: 3 }}>
        <CardContent sx={{ p: 3 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            
            <Box sx={{ flex: 1 }}>
              
              <TextField
                fullWidth
                variant="standard"
                value={exerciseName}
                onChange={(e) => setExerciseName(e.target.value)}
                sx={{
                  '& .MuiInput-input': {
                    fontSize: '1.5rem',
                    fontWeight: 500,
                  },
                }}
              />
            </Box>
          </Box>

          {/* Weight Input */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Weight
            </Typography>
            <TextField
              fullWidth
              variant="outlined"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              slotProps={{
                input: {
                  endAdornment: (
                    <Typography variant="body1" color="text.secondary">
                      kg
                    </Typography>
                  ),
                },
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
          </Box>

          <Divider sx={{ my: 3 }} />

          {/* Sets Progress */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            
            
          </Box>

          {/* Sets List */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
            {sets.map((set) => (
              <Card
                key={set.id}
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  bgcolor: set.completed ? 'action.selected' : 'background.paper',
                  borderColor: set.completed ? 'primary.main' : 'divider',
                  transition: 'all 0.2s',
                }}
              >
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography
                      variant="body1"
                      sx={{
                        minWidth: 60,
                        fontWeight: 500,
                        color: set.completed ? 'primary.main' : 'text.primary',
                      }}
                    >
                      Set {set.id}
                    </Typography>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
                      <IconButton
                        size="small"
                        onClick={() => decrementReps(set.id)}
                        sx={{ bgcolor: 'action.hover' }}
                      >
                        <Remove fontSize="small" />
                      </IconButton>
                      <TextField
                        variant="outlined"
                        size="small"
                        value={set.reps}
                        onChange={(e) => updateReps(set.id, e.target.value)}
                        slotProps={{
                          input: {
                            endAdornment: (
                              <Typography variant="caption" color="text.secondary">
                                reps
                              </Typography>
                            ),
                          },
                        }}
                        sx={{
                          width: 120,
                          '& .MuiOutlinedInput-root': {
                            borderRadius: 2,
                          },
                        }}
                      />
                      <IconButton
                        size="small"
                        onClick={() => incrementReps(set.id)}
                        sx={{ bgcolor: 'action.hover' }}
                      >
                        <Add fontSize="small" />
                      </IconButton>
                    </Box>

                    <IconButton
                      onClick={() => toggleSetCompletion(set.id)}
                      sx={{
                        bgcolor: set.completed ? 'primary.main' : 'action.hover',
                        color: set.completed ? 'primary.contrastText' : 'text.primary',
                        '&:hover': {
                          bgcolor: set.completed ? 'primary.dark' : 'action.selected',
                        },
                      }}
                    >
                      {set.completed ? <Done /> : <Close />}
                    </IconButton>
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>

          <Divider sx={{ my: 3 }} />

          {/* Progress Chart */}
          <Box sx={{ mb: 3 }}>
            
            <Box sx={{ bgcolor: '#F8F6FA', borderRadius: 2, p: 2 }}>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={chartData}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="0" stroke="#E6E1E5" vertical={false} />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#49454F', fontSize: 12 }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#49454F', fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#FFFBFE',
                      border: '1px solid #E6E1E5',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value, name) => {
                      const setNumber = name.toString().replace('set', 'Set ');
                      return [`${value} reps`, setNumber];
                    }}
                  />
                  <Bar dataKey="set1" stackId="a" fill={setColors[0]} radius={[0, 0, 0, 0]} fillOpacity={0.95} />
                  <Bar dataKey="set2" stackId="a" fill={setColors[1]} radius={[0, 0, 0, 0]} fillOpacity={0.95} />
                  <Bar dataKey="set3" stackId="a" fill={setColors[2]} radius={[0, 0, 0, 0]} fillOpacity={0.95} />
                  <Bar dataKey="set4" stackId="a" fill={setColors[3]} radius={[0, 0, 0, 0]} fillOpacity={0.95} />
                  <Bar dataKey="set5" stackId="a" fill={setColors[4]} radius={[4, 4, 0, 0]} fillOpacity={0.95} />
                </BarChart>
              </ResponsiveContainer>
              
              {/* Chart Legend */}
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', mt: 2, flexWrap: 'wrap' }}>
                {[1, 2, 3, 4, 5].map((num) => (
                  <Box key={num} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        bgcolor: setColors[num - 1],
                        borderRadius: 0.5,
                      }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Set {num}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>

          <Divider sx={{ my: 3 }} />

          {/* Comment */}
          <Box>
            
            <TextField
              fullWidth
              multiline
              rows={3}
              variant="outlined"
              placeholder="Add notes about your workout..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}