const ADDITIVE_TYPES = ["additive", "harmonic", "stretched", "compressed", "pure"]

play_stimulus = function (stimulus) {
  note_list = stimulus["notes"]
  var n = note_list.length;
  var onsets = new Array(n).fill(0);

  for (i = 0; i < n; i ++) {
    note = note_list[i];
    if (i < n - 1) {
      onsets[i + 1] = onsets[i] + note["duration"] + note["silence"]; //2
    }
    play_note_with_delay(ACTIVE_NODES, stimulus, note, 1000 * onsets[i]);
  }
}

play_note = function (active_nodes, stimulus, note_dict) {
    var note = {...note_dict}
    var pitches = note["pitches"]
    var N = pitches.length
    var specs = stimulus["channels"][note["channel"]]["synth"]
    
    for (key in DEFAULT_PARAMS) {
      if (!(key in specs)){
        specs[key] = DEFAULT_PARAMS[key]
      }
    }

    specs["duration"] = note["duration"]

    console.assert(specs["NH"] <= specs["NH_max"], "Number of harmonics must not exceed NH_max=%d!",specs["NH_max"])
    console.assert(specs["NSH"] <= specs["NSH_max"], "Number of transpositions must not exceed NSH_max=%d!",specs["NSH_max"])
    console.assert(N <= specs["NP_max"], "Number of pitches in a chord must not exceed NP_max=%d!",specs["NP_max"])

    var weights = util_complex(specs["NH"],specs["rolloff"]);
    weights = post_pad(weights, specs["NH_max"],0)

    if (specs["type"] == "pure") {
      timbre = post_pad([weights[0]],specs["NH_max"],0)
      specs["inharmonicity"] = 2;
    } else if (specs["type"] == "harmonic"){
      timbre = weights
      specs["inharmonicity"] = 2;
    } else if (specs["type"] == "stretched"){
      timbre = weights
      specs["inharmonicity"] = 2.1;   
    } else if (specs["type"] == "compressed"){
      timbre = weights
      specs["inharmonicity"] = 1.9;
    } else if (specs["type"] == "gamelan"){
      timbre = post_pad([], specs["NH_max"],0);
      for (n=0;n<4;n++){
        timbre[n] = 1
      }
      specs["inharmonicity"] = 2;
    }
    
    if (specs["type"] == "additive" && specs["params"]["amps"].length>0){
      timbre = specs["params"]["amps"]
      console.assert(specs["NH_max"] - timbre.length >= 0, "Length of custom timbre must not exceed %d!", specs["NH_max"])
      console.assert(specs["params"]["amps"].length == specs["params"]["freqs"].length, "Number of amplitudes must be equal to number of frequency partials!")
      timbre = post_pad(timbre, specs["NH_max"],0)
    }

    freqs = []
    for (i=0;i<N;i++){
      freqs = freqs.concat([util_midi2freq(pitches[i])])
    } 

    if (INST_NAMES.includes(specs["type"])){
      var instrument = LOADED_INSTRUMENTS[specs["type"]]

      instrument.triggerAttackRelease(freqs, note["duration"])
    } else {
      freqs = post_pad(freqs,specs["NP_max"],0) // 0 frequency signifies no output
      custom_timbre_synth(active_nodes,freqs,timbre,specs)
    }  
  
}
  
util_freq2midi = function (freq) {
    return Math.log2(freq/440)*12 + 69
}

util_midi2freq = function (midi) {
    return (Math.pow(2,(midi-69)/12))*440
}

util_complex = function (NH,rolloff) {
    var partials = []
    var norm = 0

    for (i=1;i<=NH;i++){
        weight = - Math.log2(i) * rolloff
        weight = Math.pow(10,weight/20) 
        partials = partials.concat([weight])
        norm = norm + Math.pow(weight,2)
    }

    return partials.map(x => x/Math.sqrt(norm))

}

util_shepard = function (NSH,NSH_max,freq,inharmonicity) {
  var weights = []
  var norm = 0
  gamma = Math.log2(inharmonicity) // inharmonic rescaling factor

  for (n=0;n<2*NSH+1;n++){
      curr_freq = util_freq2midi(freq * Math.pow(inharmonicity,n - NSH))
      weight = util_gaussian(curr_freq,gamma*65.5,gamma*8.2) // a Gaussian weight centered at the mid point of the midi scale, rescaled if needed for inharmonic compatability
      weights = weights.concat([weight])
      norm = norm + Math.pow(weight,2)
  }

  weights = weights.map(x => x/Math.sqrt(norm))

  padding = new Array(NSH_max-NSH).fill(0); // symmetric padding around the central weights to keep a fixed size
  weights = padding.concat(weights)
  weights = weights.concat(padding)

  return weights

}

util_gaussian = function(x,mu,sigma){
  N = Math.sqrt(2*Math.PI*(sigma**2))
  return 1/N * Math.exp(-1 * ((x - mu) ** 2) / (2 * sigma ** 2))
}

custom_timbre_synth = function(active_nodes,freqs,timbre,specs){
  var ampEnv = active_nodes["envelope"];
  ampEnv.attack = specs["attack"]
  ampEnv.decay = specs["decay"]
  ampEnv.sustain = specs["sustain_amp"]
  ampEnv.release = specs["duration"] - specs["attack"] - specs["decay"]

  for (i=0;i<specs["NP_max"];i++){
    freq = freqs[i]
    tone_nodes = active_nodes["complex_" + String(i)]

    if (freq == 0) {
      sweights = post_pad([],2*specs["NSH_max"]+1,0)
    } else {
      sweights = util_shepard(specs["NSH"],specs["NSH_max"],freq,specs["inharmonicity"]) // generate shepard weight tower around freq of width NSH, and then zero-pad to width NSH_max
    }
    
    for (j=0;j<2*specs["NSH_max"]+1;j++){ 
      curr_freq = freq * Math.pow(specs["inharmonicity"],j - specs["NSH_max"]) // generate Shepard octave compatible with stretching 
      for (k=0;k<specs["NH_max"];k++){ 
        osc = tone_nodes[j][k][0]
        gain = tone_nodes[j][k][1]
        if (specs["type"] == "gamelan" && i>0) {
          freq_vals = get_custom_freqs(specs["type"],specs["NH_max"])
          osc.frequency.value = curr_freq * freq_vals[k]
        } else if (specs["type"] == "additive") {
          custom_freqs = post_pad(specs["params"]["freqs"],specs["NH_max"],0)
          osc.frequency.value = curr_freq * custom_freqs[k]
        } else {
          osc.frequency.value = curr_freq * Math.pow(specs["inharmonicity"],Math.log2(k+1))
        }
        gain.gain.value = sweights[j] * timbre[k] 
      }

    }
  }
  ampEnv.triggerAttackRelease((specs["attack"] + specs["decay"])*(1 + specs["reg"]))
}

generate_additive_nodes = function(options){

  var control_nodes = {}
  var ampEnv = new Tone.AmplitudeEnvelope({
    "attack": DEFAULT_PARAMS["attack"],
    "decay": DEFAULT_PARAMS["decay"],
    "sustain": DEFAULT_PARAMS["sustain_amp"],
    "release": DEFAULT_PARAMS["duration"] - DEFAULT_PARAMS["attack"] - DEFAULT_PARAMS["decay"],
    "attackCurve" : "linear",
    "releaseCurve" : "exponential"
  }).toDestination();

  for (i = 0; i < DEFAULT_PARAMS["NP_max"]; i++){
    var tone_nodes = util_2d_array(2*DEFAULT_PARAMS["NSH_max"]+1,DEFAULT_PARAMS["NH_max"])
    for (j=0;j<2*DEFAULT_PARAMS["NSH_max"]+1;j++){
      for (k=0;k<DEFAULT_PARAMS["NH_max"];k++){
        var osc = new Tone.Oscillator({"type": "sine", "volume": -17});
        var gain = new Tone.Gain();
        osc.connect(gain).start();
        gain.connect(ampEnv);
        tone_nodes[j][k] = [osc,gain];
      }
    }

    control_nodes["complex_" + String(i)] = tone_nodes

  }
  control_nodes["envelope"] = ampEnv
  
  return control_nodes
}

util_2d_array = function(M,N) {
  var matrix = new Array(M)
  for (m=0;m<matrix.length;m++) {
    matrix[m] = new Array(N)
  }
  return matrix
}

play_note_with_delay = function(active_nodes, stimulus, note, delay) {
  setTimeout(function() {
    play_note(active_nodes, stimulus, note);
  }, delay);
};

get_custom_freqs = function(type,NH){
  
  if (type=="gamelan"){
    freqs = [1,1.52,3.46,3.92]
    freqs = freqs.concat(new Array(NH - 4).fill(1))
  } else {
    freqs = []
  }

  return freqs
}

load_sampler = async function (synth) {
    let sampler;

    return await new Promise((resolve) => {
        let spec = {
            onload: () => resolve(sampler.toDestination())
        };
        Object.assign(spec, INSTRUMENTS[synth]);
        sampler = new Tone.Sampler(spec);
    });
}

post_pad = function (vector, target_length, num) {
  console.assert(target_length - vector.length >= 0, "Invalid target length!")
  topad = new Array(target_length - vector.length).fill(num);
  padded_vector = vector.concat(topad)
  return padded_vector
}

