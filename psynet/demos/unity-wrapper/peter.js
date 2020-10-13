Zoom Group Chat
Peter Harrison To Everyone4:56:05 PM
var makeBlue = function (elem) {

    elem.classList.add('blue');

    // Create a new event
    var event = new CustomEvent('madeBlue');

    // Dispatch the event
    elem.dispatchEvent(event);

};
var elem = document.querySelector('.not-blue');
makeBlue(elem);

// Run function on `madeBlue` event
elem.addEventListener('madeBlue', function (elem) {
    elem.classList.add('color-changed');
}, false);
