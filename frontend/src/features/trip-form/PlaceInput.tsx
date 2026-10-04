import { Autocomplete, Box, TextField, Typography } from '@mui/material'
import { MapPin } from 'lucide-react'
import { type KeyboardEvent, useEffect, useRef, useState } from 'react'

import { type PlaceOption, searchPlaces } from '../../api/client'
import type { PlaceValue } from '../../state/urlState'
import { color } from '../../theme/tokens'

const MIN_CHARS = 3
const DEBOUNCE_MS = 250

interface PlaceInputProps {
  label: string
  value: PlaceValue
  onChange: (value: PlaceValue) => void
  error?: string
  autoFocus?: boolean
}

/**
 * Type to search the US, Canada and Mexico. Picking a suggestion keeps its
 * coordinates, so the plan skips geocoding; typed text is looked up on submit.
 * Enter picks the top suggestion (or the one moved to) and never submits the
 * form, so the fields below are not skipped.
 */
export function PlaceInput({ label, value, onChange, error, autoFocus }: PlaceInputProps) {
  // The suggestions and the text they are for, so Enter never picks one for older text.
  const [results, setResults] = useState<{ query: string; places: PlaceOption[] }>({ query: '', places: [] })
  // The suggestion moved to with the arrows or the mouse, which Enter then picks.
  const highlighted = useRef<PlaceOption | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState<string>()
  // Search only after the user types here, not for text that came from a link.
  const [typed, setTyped] = useState(false)
  const text = value.label
  const searching = typed && text.trim().length >= MIN_CHARS && value.lat === undefined

  useEffect(() => {
    if (!searching) return
    const query = text.trim()
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setLoading(true)
      try {
        setResults({ query, places: await searchPlaces(query, controller.signal) })
        setSearchError(undefined)
      } catch (exc) {
        if (!controller.signal.aborted) {
          setResults({ query, places: [] })
          setSearchError((exc as Error).message)
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, DEBOUNCE_MS)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [text, searching])

  const picked = value.lat !== undefined
  const pick = (place: PlaceOption) => onChange({ label: place.label, lat: place.lat, lon: place.lon })

  const onKeyDown = (event: KeyboardEvent & { defaultMuiPrevented?: boolean }) => {
    if (event.key !== 'Enter' || event.nativeEvent.isComposing) return
    event.preventDefault()
    if (highlighted.current) return // the Autocomplete picks it
    event.defaultMuiPrevented = true
    const top = searching && results.query === text.trim() ? results.places[0] : undefined
    if (top) pick(top)
  }

  return (
    <Autocomplete<PlaceOption, false, false, true>
      freeSolo
      options={searching ? results.places : []}
      filterOptions={(all) => all}
      getOptionLabel={(option) => (typeof option === 'string' ? option : option.label)}
      inputValue={text}
      onHighlightChange={(_, option) => {
        highlighted.current = option
      }}
      onClose={() => {
        highlighted.current = null
      }}
      onKeyDown={onKeyDown}
      onInputChange={(_, next, reason) => {
        if (reason === 'input' || reason === 'clear') {
          highlighted.current = null
          setTyped(true)
          onChange({ label: next })
        }
      }}
      onChange={(_, next) => {
        if (next && typeof next !== 'string') pick(next)
      }}
      loading={searching && loading}
      loadingText="Searching…"
      noOptionsText={text.trim().length < MIN_CHARS ? 'Type at least 3 characters' : 'No matches'}
      renderOption={(props, option) => {
        const { key, ...rest } = props as typeof props & { key: string }
        return (
          <Box component="li" key={key} {...rest} sx={{ gap: 1.25 }}>
            <MapPin size={16} color={color.turquoise} />
            <Typography sx={{ fontSize: 14 }}>{option.label}</Typography>
          </Box>
        )
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          // The API takes at most 200 characters; never let a search fail on length.
          slotProps={{ ...params.slotProps, htmlInput: { ...params.slotProps.htmlInput, maxLength: 200 } }}
          size="small"
          label={label}
          autoFocus={autoFocus}
          error={Boolean(error)}
          helperText={
            error ??
            searchError ??
            (picked || !text.trim() ? undefined : 'Pick a suggestion, or plan with this text')
          }
        />
      )}
    />
  )
}
