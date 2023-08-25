document.addEventListener("DOMContentLoaded", () => {
    let parent_rect = document.getElementsByClassName("sidebar-scroll")[0].getBoundingClientRect();
    let child_rect = document.getElementsByClassName("current-page")[0].getBoundingClientRect();
    document.getElementsByClassName("sidebar-scroll")[0].scrollTo({top: child_rect.y - parent_rect.y, behavior: "instant"});
});
